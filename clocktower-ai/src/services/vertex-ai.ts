import {
  Content,
  GoogleGenerativeAI,
  Part,
  SchemaType,
} from '@google/generative-ai';
import { z } from 'zod';

import { env } from '../env';
import { PlayerBehaviorParameters, PlayerResponse } from '../clocktower/types';

export const aiClient = new GoogleGenerativeAI(env.GEMINI_API_KEY);

// Optional transport injection; preserve each player's original history API.
export type GenerationOptions = { behaviorParameters?: PlayerBehaviorParameters; timeoutMs?: number; maxAttempts?: number };
type ResponseProvider = (system: string, history: Content[], message: string | Part[], actions: string[], options?: GenerationOptions) => Promise<PlayerResponse>;
let responseProvider: ResponseProvider | undefined;
let generationParameters = {temperature:.7, topP:.95, topK:40, maxOutputTokens:1200, timeoutMs:180000, maxAttempts:3};
export function setResponseProvider(provider: ResponseProvider): void {
  responseProvider = provider;
}
export function setGenerationParameters(parameters: Partial<typeof generationParameters>): void {
  generationParameters={...generationParameters,...parameters};
}

const responseSchema = z
  .object({
    communication: z.object({intent:z.string().max(80),identityClaims:z.array(z.object({subject:z.string(),claimedRole:z.string()})).max(4),evidenceRefs:z.array(z.number().int()).max(8)}).nullable().optional(),
    memoryUpdate: z.object({beliefs:z.array(z.object({player:z.string(),summary:z.string().max(240)})).max(12),plan:z.array(z.string().max(240)).max(5),worlds:z.array(z.string().max(240)).max(5)}).nullable().optional(),
    reasoning: z.string().min(1),
    action: z.string().min(1),
    message: z.string().optional(),
    players: z.array(z.string()).optional(),
  })
  .strict();

export const generateResponse = async (
  systemInstruction: string,
  history: Content[],
  message: string | Part[],
  allowedActions: string[],
  attempt = 0,
  maxAttempts = generationParameters.maxAttempts - 1,
  options: GenerationOptions = {}
): Promise<PlayerResponse> => {
  if (responseProvider) {
    const response = responseSchema.parse(await responseProvider(systemInstruction, history, message, allowedActions, options));
    if (!allowedActions.includes(response.action)) throw new Error('Provider returned an invalid action');
    return response;
  }
  if (!env.GEMINI_API_KEY) throw new Error('Configure GEMINI_API_KEY or inject a response provider');
  try {
    const aiModel = aiClient.getGenerativeModel({
      model: process.env.GEMINI_MODEL || 'gemini-2.0-flash',
      systemInstruction,
    });

    const chatSession = aiModel.startChat({
      generationConfig: {
        temperature: generationParameters.temperature,
        topP: generationParameters.topP,
        topK: generationParameters.topK,
        maxOutputTokens: generationParameters.maxOutputTokens,
        responseMimeType: 'application/json',
        responseSchema: {
          type: SchemaType.OBJECT,
          properties: {
            reasoning: {
              type: SchemaType.STRING,
            },
            action: {
              type: SchemaType.STRING,
              format: 'enum',
              enum: allowedActions,
            },
            message: {
              type: SchemaType.STRING,
            },
            players: {
              type: SchemaType.ARRAY,
              items: {
                type: SchemaType.STRING,
              },
            },
            communication: {
              type: SchemaType.OBJECT,
              properties: {
                intent: { type: SchemaType.STRING },
                identityClaims: { type: SchemaType.ARRAY, items: { type: SchemaType.OBJECT, properties: { subject: { type: SchemaType.STRING }, claimedRole: { type: SchemaType.STRING } }, required: ['subject', 'claimedRole'] } },
                evidenceRefs: { type: SchemaType.ARRAY, items: { type: SchemaType.NUMBER } },
              },
              required: ['intent', 'identityClaims', 'evidenceRefs'],
            },
          },
          required: ['action', 'reasoning'],
        },
      },
      history: history,
    });

    const generationResult = await chatSession.sendMessage(message);
    const responseText = generationResult.response.text();

    const parsedResponse = JSON.parse(responseText);
    const validatedResponse = responseSchema.parse(parsedResponse);

    if (!allowedActions.includes(validatedResponse.action)) {
      throw new Error(
        `Invalid action: ${parsedResponse.action} [${allowedActions.join(
          ', '
        )}]`
      );
    }

    return validatedResponse;
  } catch (err: any) {
    const shouldRetry = attempt <= maxAttempts;
    console.error(
      `Failed to parse LLM response after ${attempt} attempts! ${
        shouldRetry ? 'Retrying...' : 'Giving up!'
      }`,
      err
    );

    if (shouldRetry) {
      return generateResponse(
        systemInstruction,
        history,
        message,
        allowedActions,
        attempt + 1,
        options.maxAttempts ?? maxAttempts,
        options
      );
    }

    throw new Error(`Failed to generate a response after ${attempt} attempts!`);
  }
};

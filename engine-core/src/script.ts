import type { RolePlugin } from "./roles";

export interface ScriptManifest {
  readonly id: string;
  readonly name: { en: string; zh: string };
  readonly version: number;
  readonly roles: readonly RolePlugin[];
  /** IDs are kept separately so an unimplemented role is still script-visible. */
  readonly roleIds: readonly string[];
  readonly implementedRoleIds: readonly string[];
  /** The source script's `_meta` object, retained without lossy translation. */
  readonly meta?: Readonly<Record<string, unknown>>;
  /** Alias for consumers that use the more general metadata terminology. */
  readonly metadata?: Readonly<Record<string, unknown>>;
}

export class ScriptRegistry {
  private readonly manifests = new Map<string, ScriptManifest>();

  constructor(manifests: readonly ScriptManifest[] = []) {
    for (const manifest of manifests) this.register(manifest);
  }

  register(manifest: ScriptManifest): this {
    if (!manifest.id.trim()) throw new Error("Script id is required");
    if (this.manifests.has(manifest.id)) throw new Error(`Script already registered: ${manifest.id}`);
    const roleIds = new Set<string>();
    for (const role of manifest.roles) {
      if (roleIds.has(role.id)) throw new Error(`Duplicate role ${role.id} in ${manifest.id}`);
      roleIds.add(role.id);
    }
    this.manifests.set(manifest.id, manifest);
    return this;
  }

  get(id: string): ScriptManifest {
    const manifest = this.manifests.get(id);
    if (!manifest) throw new Error(`Unknown script: ${id}`);
    return manifest;
  }

  find(id: string): ScriptManifest | undefined {
    return this.manifests.get(id);
  }

  role(scriptId: string, roleId: string): RolePlugin {
    const role = this.get(scriptId).roles.find((candidate) => candidate.id === roleId);
    if (!role) throw new Error(`Unknown role ${roleId} in ${scriptId}`);
    return role;
  }

  list(): readonly ScriptManifest[] {
    return [...this.manifests.values()];
  }
}

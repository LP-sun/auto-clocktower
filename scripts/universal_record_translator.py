#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Universal Blood on the Clocktower Record Translator
血染钟楼通用全量对局记录转译系统
================================================================================
支持转译数据源：
1. Auto-Clocktower 纯数学模型模拟轨迹文件 (trajectories.jsonl)
2. Bridge LLM 多智能体对局运行目录 (包含 events.jsonl, result.json 等)
3. 外部单局 JSON 原始记录 / 历史对局日志

核心特性：
- 自动适配多数据源 (Auto-Detection Adapter Pattern)
- 完美兼容完成与中断对局 (Incomplete Run Resilience)
- 统一输出符合 Canonical Schema 2.0 规范的 JSON 复盘
- 自动生成包含全量胜率、死因、角色指标的汇总索引清单 (manifest.json)
"""

import os
import sys
import json
import re
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ClocktowerTranslator")

# ==============================================================================
# 角色中英映射与属性字典 (Trouble Brewing Standard)
# ==============================================================================

ROLE_ZH_MAP = {
    "washerwoman": "洗衣妇", "librarian": "图书管理员", "investigator": "调查员", "chef": "厨师",
    "empath": "共情者", "fortune_teller": "占卜师", "undertaker": "送葬者", "monk": "僧侣",
    "ravenkeeper": "守鸦人", "virgin": "贞洁者", "slayer": "猎手", "soldier": "士兵", "mayor": "镇长",
    "butler": "管家", "drunk": "酒鬼", "recluse": "陌客", "saint": "圣徒",
    "poisoner": "投毒者", "spy": "间谍", "scarlet_woman": "红唇女郎", "baron": "男爵",
    "imp": "小恶魔"
}

ROLE_TYPE_MAP = {
    "washerwoman": "镇民", "librarian": "镇民", "investigator": "镇民", "chef": "镇民",
    "empath": "镇民", "fortune_teller": "镇民", "undertaker": "镇民", "monk": "镇民",
    "ravenkeeper": "镇民", "virgin": "镇民", "slayer": "镇民", "soldier": "镇民", "mayor": "镇民",
    "butler": "外来者", "drunk": "外来者", "recluse": "外来者", "saint": "外来者",
    "poisoner": "爪牙", "spy": "爪牙", "scarlet_woman": "爪牙", "baron": "爪牙",
    "imp": "恶魔"
}

ROLE_CAMP_MAP = {
    "washerwoman": "善良", "librarian": "善良", "investigator": "善良", "chef": "善良",
    "empath": "善良", "fortune_teller": "善良", "undertaker": "善良", "monk": "善良",
    "ravenkeeper": "善良", "virgin": "善良", "slayer": "善良", "soldier": "善良", "mayor": "善良",
    "butler": "善良", "drunk": "善良", "recluse": "善良", "saint": "善良",
    "poisoner": "邪恶", "spy": "邪恶", "scarlet_woman": "邪恶", "baron": "邪恶",
    "imp": "邪恶"
}

REASON_ZH_MAP = {
    "imp_dead": "小恶魔死亡且邪恶方无后备继承者，善良阵营获胜",
    "demon_in_final_two": "恶魔存活至最终两人，邪恶阵营达成残局胜算获胜",
    "saint_executed": "圣徒被投票处决出局，触发外来者即死规则，善良阵营直接判负",
    "evil_saint_executed": "圣徒被投票处决出局，触发外来者即死规则，邪恶阵营直接获胜",
    "mayor_three_alive": "场上仅剩三名玩家存活且当日无人被处决，镇长被动和平能力触发，善良阵营获胜",
    "good_eliminated": "善良玩家全员阵亡，邪恶阵营获胜",
    "evil_eliminated": "邪恶玩家全员阵亡，善良阵营获胜",
    "aborted_unspecified": "对局意外中断或异常退出（未完待续）"
}

def to_role_zh(r: Optional[str]) -> str:
    return ROLE_ZH_MAP.get(r.lower() if isinstance(r, str) else r, str(r or "未知"))

def to_role_type(r: Optional[str]) -> str:
    return ROLE_TYPE_MAP.get(r.lower() if isinstance(r, str) else r, "未知")

def to_role_camp(r: Optional[str]) -> str:
    return ROLE_CAMP_MAP.get(r.lower() if isinstance(r, str) else r, "未知")


# ==============================================================================
# 适配器基类 (Base Adapter)
# ==============================================================================

class BaseGameAdapter(ABC):
    """所有记录解析适配器的抽象基类"""

    @abstractmethod
    def can_handle(self, source_path: Path) -> bool:
        """判断当前适配器是否能够处理该路径"""
        pass

    @abstractmethod
    def extract_games(self, source_path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """从源路径中提取并转译出标准 JSON 对象列表"""
        pass


# ==============================================================================
# 适配器 1: 数学模型轨迹适配器 (Math Trajectory Adapter)
# ==============================================================================

class MathTrajectoryAdapter(BaseGameAdapter):
    """处理 E:/auto-clocktower/output/trajectories.jsonl 类的纯数学模拟对局"""

    def can_handle(self, source_path: Path) -> bool:
        if source_path.is_file() and source_path.name.endswith(".jsonl") and source_path.name != "events.jsonl":
            try:
                with open(source_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline()
                    if not first_line:
                        return False
                    data = json.loads(first_line)
                    return 'true_roles' in data and 'events' in data and 'seed' in data
            except Exception:
                return False
        return False

    def extract_games(self, source_path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        games = []
        with open(source_path, 'r', encoding='utf-8') as f:
            for line_idx, line in enumerate(f):
                if not line.strip():
                    continue
                if limit and len(games) >= limit:
                    break
                raw = json.loads(line)
                canon = self._convert_single(raw, str(source_path), line_idx)
                games.append(canon)
        return games

    def _convert_single(self, raw: Dict[str, Any], file_path: str, index: int) -> Dict[str, Any]:
        seed = raw.get('seed', index)
        winner = raw.get('winner', 'undecided')
        end_reason = raw.get('end_reason', 'aborted_unspecified')
        total_days = raw.get('total_days', 0)
        true_roles = raw.get('true_roles', {})
        events = raw.get('events', [])

        game_id = f"math_sim_seed_{seed}_{end_reason}"

        # 1. 抽取全局配置与开局属性
        start_ev = next((e for e in events if e.get('type') == 'GAME_START'), None)
        start_data = start_ev.get('data', {}) if start_ev else {}
        imp_bluffs = [to_role_zh(b) for b in start_data.get('imp_bluffs', [])]
        drunk_fake = to_role_zh(start_data.get('drunk_fake_role')) if start_data.get('drunk_fake_role') else None

        # 2. 追踪玩家死亡与行动流水
        player_deaths = {}
        player_actions = {p: [] for p in true_roles}
        special_mechanics = []

        for ev in events:
            t = ev.get('type')
            day = ev.get('day', 0)
            actor = ev.get('actor')
            target = ev.get('target')
            data = ev.get('data', {})

            if t == 'DEATH':
                player_deaths[actor] = {
                    'day': day,
                    'phase': ev.get('phase', 'unknown'),
                    'reason': data.get('reason')
                }
            elif t == 'SLAYER_SHOT':
                res = "成功命中" if data.get('success') else "未命中"
                player_actions[actor].append(f"第 {day} 天发动猎手技能狙杀 {target}（{res}）")
                special_mechanics.append("slayer_shot")
            elif t == 'VIRGIN_PROC':
                player_actions[actor].append(f"第 {day} 天被 {target} 提名触发贞洁者神裁反噬处决")
                special_mechanics.append("virgin_proc")
            elif t == 'ST_REGISTRATION':
                player_actions[actor].append(f"第 {day} 天被说书人判定注册为 {to_role_zh(data.get('registered_as'))}")
                special_mechanics.append("st_registration")

        # 3. 构造玩家底牌列表
        players_list = []
        for p in sorted(true_roles.keys(), key=lambda x: int(x[1:]) if x[1:].isdigit() else x):
            role_id = true_roles[p]
            d_info = player_deaths.get(p)
            alive = d_info is None
            players_list.append({
                "seat": p,
                "player_id": p,
                "role_id": role_id,
                "role_zh": to_role_zh(role_id),
                "camp": to_role_camp(role_id),
                "role_type": to_role_type(role_id),
                "final_status": "alive" if alive else "dead",
                "death_info": d_info,
                "claims_history": [],
                "key_actions": player_actions.get(p, [])
            })

        # 4. 按天构建时间线
        days_map = {}
        for ev in events:
            d = ev.get('day', 0)
            days_map.setdefault(d, []).append(ev)

        timeline = []
        for d in sorted(days_map.keys()):
            evs = days_map[d]
            dawn_ev = next((e for e in evs if e.get('type') == 'DAWN'), None)
            alive_players = dawn_ev.get('data', {}).get('alive_players', []) if dawn_ev else []
            threshold = dawn_ev.get('data', {}).get('execution_threshold') if dawn_ev else None

            day_obj = {
                "day": d,
                "phase_name": "准备阶段 / 首夜" if d == 0 else f"第 {d} 天",
                "alive_count": len(alive_players),
                "alive_players": alive_players,
                "execution_threshold": threshold,
                "night_events": [],
                "day_events": {
                    "speeches": [],
                    "nominations": [],
                    "special_triggers": [],
                    "deaths": [],
                    "execution": None
                }
            }

            for ev in evs:
                t = ev.get('type')
                actor = ev.get('actor')
                target = ev.get('target')
                data = ev.get('data', {})

                if t == 'NIGHT_ACTION':
                    day_obj['night_events'].append({
                        "type": "night_action",
                        "actor": actor,
                        "role": to_role_zh(data.get('role')),
                        "target": target,
                        "description": f"{actor}（{to_role_zh(data.get('role'))}）选择目标: {target}"
                    })
                elif t in ['INFO_WASHERWOMAN', 'INFO_LIBRARIAN', 'INFO_INVESTIGATOR', 'INFO_CHEF', 'INFO_EMPATH', 'INFO_FORTUNE_TELLER', 'INFO_RAVENKEEPER']:
                    day_obj['night_events'].append({
                        "type": "night_info",
                        "actor": actor,
                        "info_type": t,
                        "raw_data": data,
                        "description": f"{actor} 获得能力信息: {json.dumps(data, ensure_ascii=False)}"
                    })
                elif t == 'NOMINATION':
                    day_obj['day_events']['nominations'].append({
                        "nominator": actor,
                        "nominee": target,
                        "votes_for": None,
                        "threshold": threshold,
                        "exceeded": None
                    })
                elif t == 'VOTE_RESULT':
                    if day_obj['day_events']['nominations']:
                        day_obj['day_events']['nominations'][-1]["votes_for"] = data.get('votes')
                        day_obj['day_events']['nominations'][-1]["exceeded"] = data.get('exceeded')
                elif t in ['VIRGIN_PROC', 'SLAYER_SHOT', 'ST_REGISTRATION']:
                    day_obj['day_events']['special_triggers'].append({
                        "type": t,
                        "actor": actor,
                        "target": target,
                        "data": data
                    })
                elif t == 'DEATH':
                    reason_desc = {
                        'demon_kill': "夜间被恶魔击杀",
                        'execution': "白天被票决处决",
                        'virgin_proc': "提名贞洁者被神裁处决",
                        'slayer_shot': "被猎手技能狙杀"
                    }.get(data.get('reason'), data.get('reason'))
                    day_obj['day_events']['deaths'].append({
                        "player": actor,
                        "reason": data.get('reason'),
                        "description": f"{actor} 死亡（{reason_desc}）"
                    })
                elif t == 'EXECUTION':
                    day_obj['day_events']['execution'] = {
                        "executed_player": actor,
                        "role": to_role_zh(data.get('role')),
                        "description": f"{actor} 被票决处决出局"
                    }

            timeline.append(day_obj)

        win_camp = "善良阵营" if winner == 'good' else ("邪恶阵营" if winner == 'evil' else "未定局")

        return {
            "schema_version": "2.0.0",
            "game_id": game_id,
            "source_meta": {
                "engine_type": "math_simulation",
                "source_path": file_path,
                "model": None,
                "seed": seed,
                "is_completed": True,
                "interruption_reason": None,
                "translated_at": datetime.now().isoformat()
            },
            "game_info": {
                "script": "暗流涌动 (Trouble Brewing)",
                "player_count": len(true_roles),
                "total_days": total_days,
                "winner": winner,
                "winning_camp": win_camp,
                "end_reason_code": end_reason,
                "end_reason_description": REASON_ZH_MAP.get(end_reason, end_reason)
            },
            "setup": {
                "townsfolk_count": sum(1 for r in true_roles.values() if to_role_type(r) == '镇民'),
                "outsiders_count": sum(1 for r in true_roles.values() if to_role_type(r) == '外来者'),
                "minions_count": sum(1 for r in true_roles.values() if to_role_type(r) == '爪牙'),
                "demon_count": sum(1 for r in true_roles.values() if to_role_type(r) == '恶魔'),
                "imp_bluffs": imp_bluffs,
                "drunk_fake_role": drunk_fake,
                "red_herring": None
            },
            "players": players_list,
            "timeline": timeline,
            "metrics": {
                "total_nominations": sum(len(d['day_events']['nominations']) for d in timeline),
                "total_executions": sum(1 for d in timeline if d['day_events']['execution']),
                "total_night_kills": len([d for d in player_deaths.values() if d.get('reason') == 'demon_kill']),
                "special_mechanics_triggered": list(set(special_mechanics))
            }
        }


# ==============================================================================
# 适配器 2: Bridge LLM 对局运行目录适配器 (Bridge Run Adapter)
# ==============================================================================

class BridgeRunAdapter(BaseGameAdapter):
    """处理包含 events.jsonl, result.json, COMPLETED 等文件的 Bridge LLM 对局目录"""

    def can_handle(self, source_path: Path) -> bool:
        if source_path.is_dir():
            events_file = source_path / "events.jsonl"
            result_file = source_path / "result.json"
            return events_file.exists() or result_file.exists()
        elif source_path.is_file() and source_path.name in ["events.jsonl", "result.json"]:
            return True
        return False

    def extract_games(self, source_path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        run_dir = source_path.parent if source_path.is_file() else source_path
        events_file = run_dir / "events.jsonl"
        result_file = run_dir / "result.json"
        config_file = run_dir / "config.json"
        comp_file = run_dir / "COMPLETED"
        inter_file = run_dir / "INTERRUPTED"

        # 1. 读取 result.json
        res_data = {}
        if result_file.exists():
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    res_data = json.load(f)
            except Exception as e:
                logger.warning(f"读取 result.json 失败: {e}")

        # 2. 读取 config.json
        config_data = {}
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except Exception as e:
                pass

        # 3. 逐行读取 events.jsonl，提取日历、事件与确凿死亡
        events = []
        assignment_event = None
        detected_deaths = {}
        max_day = 0

        if events_file.exists():
            with open(events_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    ev = json.loads(line)
                    events.append(ev)

                    if ev.get('type') == 'assignment':
                        assignment_event = ev

                    sem = ev.get('event', {}) if isinstance(ev.get('event'), dict) else {}
                    sem_type = sem.get('type')
                    d = sem.get('day')
                    if d is None:
                        d = ev.get('day', 0)
                    if isinstance(d, int) and d > max_day:
                        max_day = d

                    # 精确识别真实死亡事件 (仅针对语义类型为 death 的通知)
                    if sem_type == 'death':
                        msg_text = sem.get('text', '')
                        p_matches = re.findall(r'\*\*(P\d{2})\*\*', msg_text)
                        for p in p_matches:
                            if p not in detected_deaths:
                                is_exec = '⚰️' in msg_text or '处决' in msg_text
                                detected_deaths[p] = {
                                    'day': d,
                                    'reason': "白天处决出局" if is_exec else "夜间恶魔击杀"
                                }

        # 4. 解析角色底牌
        true_roles = {}
        imp_bluffs = []
        red_herring = None

        # 方式 A: 检查 result.json 中的 initialAssignment
        init_assign = res_data.get('initialAssignment', [])
        if isinstance(init_assign, list) and len(init_assign) > 0:
            for item in init_assign:
                p_id = item.get('player')
                role = item.get('role')
                if p_id and role:
                    true_roles[p_id] = role.lower()
        
        # 方式 B: 从 assignment 事件读取
        if not true_roles and assignment_event:
            players_data = assignment_event.get('players', [])
            if isinstance(players_data, list) and len(players_data) > 0:
                for item in players_data:
                    p = item.get('player')
                    r = item.get('role')
                    if p and r:
                        true_roles[p] = r.lower() if isinstance(r, str) else str(r)
            
            payload = assignment_event.get('payload', {})
            assignments = assignment_event.get('assignments') or payload.get('assignments', {})
            if isinstance(assignments, dict) and len(assignments) > 0:
                for p, r in assignments.items():
                    true_roles[p] = r.lower() if isinstance(r, str) else str(r)

            bluffs_raw = assignment_event.get('bluffs') or payload.get('bluffs', [])
            imp_bluffs = [to_role_zh(b) for b in bluffs_raw]
            red_herring = assignment_event.get('redHerring') or assignment_event.get('red_herring') or payload.get('red_herring')

        # 5. 解析胜负结果与中断状态
        is_completed = False
        winner = "undecided"
        end_reason = "aborted_unspecified"
        interruption_reason = None

        if comp_file.exists():
            is_completed = True

        verdict = res_data.get('verdict', {})
        if verdict and isinstance(verdict, dict):
            team = verdict.get('team')
            if team:
                winner = team
                is_completed = True
                end_reason = verdict.get('kind', 'completed_standard')

        if not is_completed:
            if inter_file.exists():
                try:
                    with open(inter_file, 'r', encoding='utf-8') as f:
                        interruption_reason = f.read().strip()
                except:
                    interruption_reason = "INTERRUPTED tag found"
            elif res_data.get('error'):
                interruption_reason = res_data.get('error')
            else:
                interruption_reason = "未见胜利结算事件，进程异常退出"

        game_id = run_dir.name
        seed = res_data.get('seed') or config_data.get('seed')
        model = config_data.get('model') or res_data.get('model') or "LLM"

        # 6. 解析终局玩家状态
        final_players = {p["player"]["userId"]: p for p in res_data.get("finalPlayers", []) if "player" in p}
        players_list = []
        for p in sorted(true_roles.keys(), key=lambda x: int(x[1:]) if x[1:].isdigit() else x):
            role_id = true_roles[p]
            fp = final_players.get(p)
            if fp:
                alive = fp.get('alive', True)
                death_info = {"reason": fp.get('deathReason', 'unknown')} if not alive else None
            else:
                d_detected = detected_deaths.get(p)
                alive = d_detected is None
                death_info = d_detected if not alive else None

            players_list.append({
                "seat": p,
                "player_id": p,
                "role_id": role_id,
                "role_zh": to_role_zh(role_id),
                "camp": to_role_camp(role_id),
                "role_type": to_role_type(role_id),
                "final_status": "alive" if alive else "dead",
                "death_info": death_info,
                "claims_history": [],
                "key_actions": []
            })

        # 7. 逐日时间线归纳
        timeline_days = {}
        for ev in events:
            sem = ev.get('event', {}) if isinstance(ev.get('event'), dict) else {}
            d = sem.get('day')
            if d is None:
                d = ev.get('day', 0)
            timeline_days.setdefault(d, []).append(ev)

        timeline = []
        for d in sorted(timeline_days.keys()):
            evs = timeline_days[d]
            day_obj = {
                "day": d,
                "phase_name": f"第 {d} 天" if d > 0 else "准备阶段 / 首夜",
                "alive_count": len(true_roles),
                "alive_players": list(true_roles.keys()),
                "execution_threshold": None,
                "night_events": [],
                "day_events": {
                    "speeches": [],
                    "nominations": [],
                    "special_triggers": [],
                    "deaths": [],
                    "execution": None
                }
            }

            for ev in evs:
                if ev.get('type') == 'semantic_event':
                    sem = ev.get('event', {})
                    stype = sem.get('type')
                    if stype in ['chat', 'whisper']:
                        day_obj['day_events']['speeches'].append({
                            "speaker": sem.get('actor') or sem.get('speaker') or sem.get('from'),
                            "type": stype,
                            "text": sem.get('text', '')
                        })
                    elif stype == 'nomination':
                        day_obj['day_events']['nominations'].append({
                            "nominator": sem.get('actor'),
                            "nominee": sem.get('target'),
                            "reason": sem.get('reason', '')
                        })
                    elif stype == 'death':
                        day_obj['day_events']['deaths'].append({
                            "description": sem.get('text', '')
                        })

            timeline.append(day_obj)

        win_camp = "善良阵营" if winner == 'good' else ("邪恶阵营" if winner == 'evil' else "未完待续 / 中断")

        canon = {
            "schema_version": "2.0.0",
            "game_id": game_id,
            "source_meta": {
                "engine_type": "bridge_llm",
                "source_path": str(run_dir),
                "model": model,
                "seed": seed,
                "is_completed": is_completed,
                "interruption_reason": interruption_reason,
                "translated_at": datetime.now().isoformat()
            },
            "game_info": {
                "script": "暗流涌动 (Trouble Brewing)",
                "player_count": len(true_roles),
                "total_days": max_day or res_data.get('night', 0),
                "winner": winner,
                "winning_camp": win_camp,
                "end_reason_code": end_reason,
                "end_reason_description": REASON_ZH_MAP.get(end_reason, interruption_reason or "正常结算")
            },
            "setup": {
                "townsfolk_count": sum(1 for r in true_roles.values() if to_role_type(r) == '镇民'),
                "outsiders_count": sum(1 for r in true_roles.values() if to_role_type(r) == '外来者'),
                "minions_count": sum(1 for r in true_roles.values() if to_role_type(r) == '爪牙'),
                "demon_count": sum(1 for r in true_roles.values() if to_role_type(r) == '恶魔'),
                "imp_bluffs": imp_bluffs,
                "drunk_fake_role": None,
                "red_herring": red_herring
            },
            "players": players_list,
            "timeline": timeline,
            "metrics": {
                "total_nominations": sum(len(d['day_events']['nominations']) for d in timeline),
                "total_executions": 0,
                "total_night_kills": 0,
                "special_mechanics_triggered": []
            }
        }
        return [canon]


# ==============================================================================
# 批量协调器与主引擎 (Batch Orchestrator)
# ==============================================================================

class UniversalRecordTranslator:
    """全量对局转译与管理引擎"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.adapters: List[BaseGameAdapter] = [
            MathTrajectoryAdapter(),
            BridgeRunAdapter()
        ]

    def scan_and_translate(self, root_paths: List[str], dry_run: bool = False, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        扫描一个或多个路径，提取全部对局记录并转译为标准 JSON
        注意：当 dry_run=True 时，仅探测与统计，不落盘写入任何文件。
        """
        all_games = []
        stats = {
            "total_sources_scanned": 0,
            "total_games_extracted": 0,
            "math_sim_games": 0,
            "bridge_llm_games": 0,
            "completed_games": 0,
            "incomplete_games": 0,
            "files_written": []
        }

        for r_path_str in root_paths:
            r_path = Path(r_path_str)
            if not r_path.exists():
                logger.warning(f"路径不存在，跳过: {r_path}")
                continue

            targets = []
            # 1. 检查根路径自身是否可直接被适配器处理
            is_handled_directly = False
            for adapter in self.adapters:
                if adapter.can_handle(r_path):
                    targets.append(r_path)
                    is_handled_directly = True
                    break

            # 2. 若根路径为目录且未被直接处理，递归探测子目录与文件
            if not is_handled_directly and r_path.is_dir():
                run_dirs = set()
                for ef in r_path.glob("**/events.jsonl"):
                    run_dirs.add(ef.parent)
                for rf in r_path.glob("**/result.json"):
                    run_dirs.add(rf.parent)
                targets.extend(list(run_dirs))

                for jf in r_path.glob("**/*.jsonl"):
                    if jf.name != "events.jsonl":
                        targets.append(jf)

            for target in targets:
                if limit and len(all_games) >= limit:
                    break
                stats["total_sources_scanned"] += 1
                for adapter in self.adapters:
                    if adapter.can_handle(target):
                        try:
                            cur_limit = (limit - len(all_games)) if limit else None
                            games = adapter.extract_games(target, limit=cur_limit)
                            for g in games:
                                stats["total_games_extracted"] += 1
                                e_type = g["source_meta"]["engine_type"]
                                if e_type == "math_simulation":
                                    stats["math_sim_games"] += 1
                                elif e_type == "bridge_llm":
                                    stats["bridge_llm_games"] += 1

                                if g["source_meta"]["is_completed"]:
                                    stats["completed_games"] += 1
                                else:
                                    stats["incomplete_games"] += 1

                                all_games.append(g)
                            break
                        except Exception as e:
                            logger.error(f"解析 {target} 失败: {str(e)}")

        logger.info(f"扫描完毕！共提取对局: {len(all_games)} 局 (完成: {stats['completed_games']} | 中断: {stats['incomplete_games']})")

        # 若非 dry_run，执行落盘
        if not dry_run:
            manifest_items = []
            for g in all_games:
                gid = g["game_id"]
                fname = f"recap_{gid}.json"
                out_file = self.output_dir / fname
                with open(out_file, 'w', encoding='utf-8') as f:
                    json.dump(g, f, ensure_ascii=False, indent=2)
                stats["files_written"].append(str(out_file))

                manifest_items.append({
                    "game_id": gid,
                    "engine_type": g["source_meta"]["engine_type"],
                    "winner": g["game_info"]["winner"],
                    "end_reason": g["game_info"]["end_reason_code"],
                    "total_days": g["game_info"]["total_days"],
                    "is_completed": g["source_meta"]["is_completed"],
                    "json_file": fname
                })

            manifest_path = self.output_dir / "manifest.json"
            with open(manifest_path, 'w', encoding='utf-8') as mf:
                json.dump({
                    "generated_at": datetime.now().isoformat(),
                    "total_games": len(all_games),
                    "summary": stats,
                    "games": manifest_items
                }, mf, ensure_ascii=False, indent=2)
            logger.info(f"汇总索引已保存至: {manifest_path}")

        return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="血染钟楼通用全量对局记录转译系统 (Canonical JSON Translator)")
    parser.add_argument("--inputs", nargs="+", required=True, help="输入路径列表 (文件或目录)")
    parser.add_argument("--output", default="./canonical_recaps", help="转译 JSON 输出目录")
    parser.add_argument("--dry-run", action="store_true", help="仅扫描统计，不写入文件")
    parser.add_argument("--limit", type=int, default=None, help="最大转换局数限制 (测试用)")
    args = parser.parse_args()

    translator = UniversalRecordTranslator(args.output)
    stats = translator.scan_and_translate(args.inputs, dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# CY-CharmYee naming and migration

The Chinese name is **承意**, the English name is **CY-CharmYee**, and the exact Chinese tagline is **承你所想，会你所意**.

The main Skill ID is `cy-charmyee`. Child display names are `CY-transcribe`, `CY-analyze`, `CY-download`, `CY-write`, `CY-knowledge` and `CY-vault`; directory names and `$cy-*` invocations are lowercase to follow host requirements. `douyin_text` remains the internal media engine module.

From 1.6.0, fresh installations use `cy-charmyee` for default workspace and state directories. Packages use `cy-charmyee-windows-v<version>.zip` and the internal root `cy-charmyee/`. Historical assets from v1.5.0 and earlier retain their names; renaming the repository does not turn those packages into new CY-CharmYee packages.

For the first cross-brand migration, the Agent runs `scripts/install.ps1` from the CY-CharmYee 1.6.0 package or its source. This also applies to old-brand versions 1.1.0–1.5.0, which already have an updater: it pins the old product ID, ZIP name, and archive root, so the legacy `update --apply` cannot install the new-brand package directly. Once CY-CharmYee is installed, later releases use the normal `update --apply` path.

1. Get the CY-CharmYee installation ZIP and matching SHA-256 from the [official Releases](https://github.com/ScarfaceAI/CY-CharmYee/releases/latest), verify and extract it, then confirm `name=cy-charmyee` in `bundle.json`.
2. Run the new installer as the same Windows user, retaining custom Agent and SkillsRoot arguments. A single existing registration needs no repeated Workspace / StateDirectory; retain an explicit state argument if the old installation used a custom state location.
3. Check the workspace, version, entrypoint, and backups in the installation receipt. Run `doctor` through the returned `entrypoint`, then use existing text to verify continuation of the same task.
4. Reread the new `SKILL.md` or start a new conversation. New entries use `cy-*`; old paths use the compatibility forwarding described below.

The installer reuses registered workspaces, credentials and task history. It backs up configuration, managed entrypoints and existing programs, then converts verified `dyb-*` and `douyin-brain` installations into forwarding aliases. These aliases disable implicit invocation on hosts that support it. Local additions remain in the backups recorded in the installation receipt.

`CY_WORKSPACE`, `CY_STATE_DIR` and `CY_UPDATE_CHECK` take precedence over legacy `DYB_*` values. Existing state directories, task IDs, media caches, vault locations and persisted compatibility markers remain usable. Registration refreshes owned workspace and opted-in personal-vault hooks while preserving user prose, original answers and prior choices.

Multiple workspace registrations require one explicit selection. A failed migration restores replaced programs, aliases and registration files. Local installation receipts do not establish cloud speech access or actual discovery in every host. Historical release notes and verification records preserve the names used at the time; user-selected local paths are not relocated just to match the new brand.

中文：[承意命名与迁移](brand-migration.md)。

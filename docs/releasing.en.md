# Maintenance and releases

[中文](RELEASING.md)

This guide covers maintenance, publishing, and [upgrading an existing installation](#upgrading-an-existing-installation). The public repository is the release source of truth; installed Skill copies are used to run the product.

## Changes versus releases

Routine fixes and features can be implemented and validated without increasing the version every time. A request to change a feature authorizes the change and appropriate checks; pushing, merging, and publishing require an explicit request to publish or update GitHub. Once release is authorized, complete that scope without repeatedly asking.

If work begins in an older private Skill, compare the changes and port the needed program and documentation changes into the public source individually. Check compatibility and test them. Do not overwrite the repository with an installed copy or transfer credentials, browser state, media, cache, or task data.

## Work on a branch and open a PR

1. Start from current `main` on a `codex/...`, `feat/...`, or `fix/...` branch. Implement the change and update affected documentation.
2. Run checks appropriate to the change. Whenever packaged source or documentation changes, run `python -B -X utf8 scripts/package.py --manifest-only` to update `bundle.json`, even if no release is planned. Check that the manifest includes the intended files and no user data.
3. Open a PR following [CONTRIBUTING.md](../CONTRIBUTING.md). Describe the change, actual validation, and any installation, configuration, or data migration implications.
4. Wait for the PR's `Windows / Python 3.12` check to succeed, keep the branch up to date with `main`, resolve conversations, and squash merge.

The current `main` rules require a PR, the named Windows check, an up-to-date branch, and resolved conversations; there is no additional mandatory approval count for the individual maintainer. Check the actual GitHub settings if the rules change.

## Prepare a version

For a release, include these in the PR:

- `VERSION`: follow [semantic versioning](https://semver.org/). Use PATCH for backward-compatible fixes, MINOR for backward-compatible features, and MAJOR for breaking changes. Assess installation arguments, data formats, and promised behavior the same way.
- `CHANGELOG.md` and `docs/releases/vX.Y.Z.md`: describe the change, any upgrade considerations, actual validation, and unverified scenarios. Release notes must cover both Chinese and English.
- `bundle.json`: once packaged files are final, run `python -B -X utf8 scripts/package.py --manifest-only`.

Run tests appropriate to the change and ensure every claimed result has evidence. Do not claim live speech recognition, complete creator-profile pagination, or Agent sessions passed if they were not tested. Finish these changes and checks before the PR is merged.

## Publish after merging

Publishing requires Git, Python 3.12 or later, GitHub CLI (`gh`), and network access. Authenticate `gh` as an account with repository read and tag-push access; `gh auth status` shows its login status.

After squash merge, confirm the current `main` commit contains the intended changes and wait for its `check.yml` **push** workflow to succeed. A passing PR check alone does not validate the merge commit.

Use a clean local `main` matching `origin/main`, then run the preflight:

```powershell
git fetch origin main --tags
git switch main
git pull --ff-only origin main
python -B -X utf8 scripts/release.py
```

The default invocation only checks readiness; it does not create a release tag. It checks the working tree and branch, `VERSION`, changelog, corresponding bilingual release notes, package manifest, successful `check.yml` push CI on the current remote `main` commit, and that the version is newer than previous stable tags. Resolve any reported problem without discarding existing work.

When the user has explicitly requested a release, run:

```powershell
python -B -X utf8 scripts/release.py --publish
```

After successful preflight, this creates and pushes the `vX.Y.Z` tag, triggering GitHub Actions to build and publish. Use the output's Actions link to find the run for this tag; wait in the browser or with `gh run watch <run-id>`. Once it succeeds and the Release appears, verify the public download:

```powershell
python -B -X utf8 scripts/verify_release.py --download
```

The verifier downloads the current `VERSION` ZIP and SHA to `.scratch` and checks the SHA, ZIP CRC, complete file set, and consistency of the packaged `bundle.json` with the source. To verify a local package instead, put its matching `.zip.sha256` file beside the ZIP. The local package must also match the current source version and manifest:

```powershell
python -B -X utf8 scripts/verify_release.py --archive '<path-to-local-zip>'
```

Report the release and package verification as complete only after the public download check succeeds. Separately identify scenarios the checks did not establish, such as live speech service, complete profile pagination, and individual Agent sessions.

Record post-release evidence in project documentation, including the tag, source commit, CI, and package SHA; do not leave it only in `.scratch`. See the [1.1.1 verification snapshot](verification/v1.1.1.md).

If `main` contains documentation changes made after a release, reverify that release from a separate checkout of its tag: `verify_release.py` strictly compares against the current source manifest. Do not overwrite an old Release to make it match. Independently built ZIPs may have different whole-archive SHAs because of timestamps; verify each ZIP against its own `.zip.sha256` checksum file and the source manifest for its tag.

## Upgrading an existing installation

### First migration from the old brand to CY-CharmYee 1.6.0

Every old-brand `dyb-douyinbrain` or `douyin-brain` installation must run the new installer once to switch to CY-CharmYee. Versions 1.0.0 and 1.0.1 have no updater. Versions 1.1.0–1.5.0 have one, but it pins the old product ID, ZIP name, and archive root, so their legacy `update --apply` cannot directly install the 1.6.0 new-brand package.

1. Download the CY-CharmYee ZIP and `.zip.sha256` from the [official Releases](https://github.com/ScarfaceAI/CY-CharmYee/releases/latest), verify them, and extract the package. The 1.6.0 file is `cy-charmyee-windows-v1.6.0.zip`, and `bundle.json` identifies `cy-charmyee`.
2. Run the installer from that new package as the same Windows user. For a default installation, double-click `install.cmd`. Retain custom Agent, SkillsRoot, or StateDirectory arguments, or have your Agent reuse them. A single registered workspace is reused automatically; multiple workspaces require one selection. Do not first delete old programs, configuration, or tasks.
3. Run `doctor` using the `entrypoint` from the installation result, then check actual behavior with a low-impact task such as an existing text of your choice. A live speech test requires authorized material and may incur charges.
4. Ask the Agent to reread the installed `SKILL.md`, or start a new conversation. Updating files does not automatically replace a previously loaded Skill in the current context.

Old entries become compatibility forwarders, retaining tasks, credentials, and knowledge-base choices. See [brand migration](../references/brand-migration.en.md). Historical Release assets and tags keep their original identities.

### Already on CY-CharmYee 1.6.0 or later

After the cross-brand migration above, later updates use CY-CharmYee's normal updater. When a new task starts, the Skill checks GitHub for the latest stable release and notifies you if an update is available; it does not install automatically. Checks use a 24-hour cache. `plan` and `plan-text` notify at most once a day for the same new version. An offline or failed check does not block the original task; media downloads and cloud speech recognition still need their respective network access.

To update, say “`@cy-charmyee 更新`” or “`$cy-charmyee 更新`”; if your Agent does not support those forms, say “Use cy-charmyee to update itself.” When explicitly requested, the program downloads the official Release ZIP, checks its external SHA-256 and complete internal manifest, and runs the installer using the installed Skill's real location, existing workspace, and local state. The installer preserves backups of local program changes and keeps existing data. Afterwards, run local `doctor` and an appropriate functional check, then ask the Agent to reread the new `SKILL.md` or start a new conversation.

For a manual check or diagnosis, use the installed Skill's entry point:

```powershell
$cyRun = '<installed cy-charmyee>\scripts\invoke.ps1'
& $cyRun check-update          # Uses the 24-hour cache
& $cyRun check-update --force  # Forces a query
& $cyRun update                # Checks only; does not install
& $cyRun update --apply        # Only after the user explicitly requests an update
```

Set `$env:CY_UPDATE_CHECK = '0'` to disable routine checks for the current PowerShell process and its children. Explicit `update --apply` remains available.

The installer and `doctor` report local status only. `awaiting_api` indicates missing speech credentials and still allows existing-text work. See [INSTALL.md](../INSTALL.md) for configuration and arguments.

## Failures, fixes, and rollback

- If a GitHub certificate-chain error prevents version 1.1.0 from checking or applying an update, download the new ZIP from the [latest Release](https://github.com/ScarfaceAI/CY-CharmYee/releases/latest), follow the manual upgrade steps above using the same Windows user and original installation arguments, then check the local entry point.
- Do not rewrite or delete official `v*` tags. Preserve published Releases and assets; do not overwrite an older tag or asset after a failure.
- If tagging or publication is interrupted, inspect the Actions run and Release for that tag before choosing the next step.
- For a defect in a published version, fix it in a new PR and publish a new patch. To remove a feature, use a revert PR and publish a new version.
- Before a user returns to an older ZIP, consult the relevant migration notes, preserve data and configuration, and check compatibility. Do not delete user data as a rollback step.

References: [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow), [Semantic Versioning 2.0.0](https://semver.org/).

# Meta Integration V3 PR Execution (Folder-Isolated)

This workspace currently has unrelated dirty changes across many folders.  
Use the path manifests below to stage only Meta V3 files for each PR track.

## Branch naming

- `codex/meta-v3-backend`
- `codex/meta-v3-dbt`
- `codex/meta-v3-frontend`
- `codex/meta-v3-airbyte`
- `codex/meta-v3-qa`
- `codex/meta-v3-docs`

## Track manifests

- `/Users/thristannewman/ADinsights/docs/project/pr-track-manifests/backend.txt`
- `/Users/thristannewman/ADinsights/docs/project/pr-track-manifests/dbt.txt`
- `/Users/thristannewman/ADinsights/docs/project/pr-track-manifests/frontend.txt`
- `/Users/thristannewman/ADinsights/docs/project/pr-track-manifests/infrastructure-airbyte.txt`
- `/Users/thristannewman/ADinsights/docs/project/pr-track-manifests/qa.txt`
- `/Users/thristannewman/ADinsights/docs/project/pr-track-manifests/docs.txt`

## Safe staging flow (repeat per track)

```bash
git switch -c codex/meta-v3-<track>
git reset
while IFS= read -r path; do
  [ -n "$path" ] && git add "$path"
done < /Users/thristannewman/ADinsights/docs/project/pr-track-manifests/<track>.txt
git status --short
```

## Suggested commits

- `feat(backend): stabilize meta read APIs and sync lifecycle`
- `feat(dbt): harden meta staging snapshots and marts`
- `feat(frontend): add resilient meta state and error handling`
- `feat(infra): align meta airbyte templates and contract checks`
- `test(qa): expand meta integration playwright coverage`
- `docs(meta): add v3 rollout tracks, evidence templates, and ops updates`

## Required reviewers

- Cross-stream: Raj
- Architecture: Mira
- Backend: Sofia
- Integrations: Maya
- dbt: Priya
- Frontend/QA UX: Lina

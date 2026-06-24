import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  createContentOpsRegionalAgent,
  listContentOpsRegionalAgents,
  listContentOpsWorkspaces,
  requestContentOpsImageGeneration,
  type ContentOpsRegion,
  type ContentOpsRegionalAgent,
  type ContentOpsWorkspaceSummary,
} from '../lib/contentOps';
import { useToastStore } from '../stores/useToastStore';
import '../styles/contentOps.css';
import '../styles/phase2.css';

const REGION_OPTIONS: { value: ContentOpsRegion; label: string; hint: string }[] = [
  { value: 'caribbean', label: 'Caribbean', hint: 'en-JM · America/Jamaica' },
  { value: 'peru_latam', label: 'Peru / LATAM', hint: 'es-PE · America/Lima' },
];

type LoadState = 'loading' | 'ready' | 'error';

function regionLabel(region: ContentOpsRegion): string {
  return region === 'peru_latam' ? 'Peru / LATAM' : 'Caribbean';
}

const RegionalAgentsPage = () => {
  const addToast = useToastStore((state) => state.addToast);
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [error, setError] = useState('');
  const [workspaces, setWorkspaces] = useState<ContentOpsWorkspaceSummary[]>([]);
  const [workspaceId, setWorkspaceId] = useState('');
  const [agents, setAgents] = useState<ContentOpsRegionalAgent[]>([]);

  const [agentName, setAgentName] = useState('');
  const [agentRegion, setAgentRegion] = useState<ContentOpsRegion>('caribbean');
  const [creating, setCreating] = useState(false);

  const [imagePrompt, setImagePrompt] = useState('');
  const [imageCount, setImageCount] = useState(1);
  const [imageAgentId, setImageAgentId] = useState('');
  const [generating, setGenerating] = useState(false);

  const loadAgents = useCallback(async (selectedWorkspaceId: string) => {
    const list = await listContentOpsRegionalAgents(selectedWorkspaceId);
    setAgents(list);
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      setLoadState('loading');
      try {
        const ws = await listContentOpsWorkspaces();
        if (!active) return;
        setWorkspaces(ws);
        const firstId = ws[0]?.id ?? '';
        setWorkspaceId(firstId);
        if (firstId) {
          await loadAgents(firstId);
        } else {
          setAgents([]);
        }
        if (active) setLoadState('ready');
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Unable to load content workspaces.');
        setLoadState('error');
      }
    })();
    return () => {
      active = false;
    };
  }, [loadAgents]);

  const handleWorkspaceChange = async (nextId: string) => {
    setWorkspaceId(nextId);
    setImageAgentId('');
    try {
      await loadAgents(nextId);
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Unable to load agents.', 'error');
    }
  };

  const handleCreateAgent = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!workspaceId) {
      addToast('Select a workspace first.', 'error');
      return;
    }
    if (!agentName.trim()) {
      addToast('Agent name is required.', 'error');
      return;
    }
    setCreating(true);
    try {
      const agent = await createContentOpsRegionalAgent({
        workspaceId,
        name: agentName,
        region: agentRegion,
      });
      setAgents((current) => [...current, agent]);
      setAgentName('');
      addToast(`Created ${agent.name} (${agent.locale}).`, 'success');
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Unable to create agent.', 'error');
    } finally {
      setCreating(false);
    }
  };

  const handleGenerateImage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!workspaceId) {
      addToast('Select a workspace first.', 'error');
      return;
    }
    if (!imagePrompt.trim()) {
      addToast('An image prompt is required.', 'error');
      return;
    }
    setGenerating(true);
    try {
      const job = await requestContentOpsImageGeneration({
        workspaceId,
        prompt: imagePrompt,
        count: imageCount,
        regionalAgentProfileId: imageAgentId || undefined,
      });
      setImagePrompt('');
      addToast(`Image job queued (${job.id}).`, 'success');
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Unable to queue image job.', 'error');
    } finally {
      setGenerating(false);
    }
  };

  if (loadState === 'loading') {
    return (
      <section className="content-ops-section">
        <p>Loading regional content agents…</p>
      </section>
    );
  }

  if (loadState === 'error') {
    return (
      <section className="content-ops-section">
        <h1>Regional content agents</h1>
        <p role="alert">{error}</p>
      </section>
    );
  }

  return (
    <div className="content-ops-page">
      <section className="content-ops-section" aria-labelledby="agents-title">
        <div className="content-ops-section__header">
          <h1 id="agents-title">Regional content agents</h1>
          <Link to="/content">Back to content operations</Link>
        </div>
        {workspaces.length === 0 ? (
          <p>Create a content workspace before configuring agents.</p>
        ) : (
          <label className="content-ops-field">
            <span>Workspace</span>
            <select
              value={workspaceId}
              onChange={(event) => void handleWorkspaceChange(event.target.value)}
            >
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </section>

      <section className="content-ops-section" aria-labelledby="agents-list-title">
        <div className="content-ops-section__header">
          <h2 id="agents-list-title">Agents</h2>
          <span>{agents.length} configured</span>
        </div>
        {agents.length === 0 ? (
          <p>No agents yet. Create one below.</p>
        ) : (
          <table className="phase2-table" aria-label="Regional agents">
            <thead>
              <tr>
                <th>Name</th>
                <th>Region</th>
                <th>Locale</th>
                <th>Language</th>
                <th>Timezone</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.id}>
                  <td>{agent.name}</td>
                  <td>{regionLabel(agent.region)}</td>
                  <td>{agent.locale}</td>
                  <td>{agent.language}</td>
                  <td>{agent.timezone}</td>
                  <td>{agent.isActive ? 'Active' : 'Inactive'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="content-ops-section" aria-labelledby="create-agent-title">
        <div className="content-ops-section__header">
          <h2 id="create-agent-title">Create agent</h2>
          <span>Locale &amp; timezone default from the region</span>
        </div>
        <form className="content-ops-generation-form" onSubmit={handleCreateAgent}>
          <label className="content-ops-field">
            <span>Name</span>
            <input
              type="text"
              value={agentName}
              disabled={creating || !workspaceId}
              onChange={(event) => setAgentName(event.target.value)}
            />
          </label>
          <label className="content-ops-field">
            <span>Region</span>
            <select
              value={agentRegion}
              disabled={creating || !workspaceId}
              onChange={(event) => setAgentRegion(event.target.value as ContentOpsRegion)}
            >
              {REGION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} — {option.hint}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={creating || !workspaceId}>
            {creating ? 'Creating…' : 'Create agent'}
          </button>
        </form>
      </section>

      <section className="content-ops-section" aria-labelledby="image-gen-title">
        <div className="content-ops-section__header">
          <h2 id="image-gen-title">Generate image</h2>
          <span>Queued for review — no render until a provider is enabled</span>
        </div>
        <form className="content-ops-generation-form" onSubmit={handleGenerateImage}>
          <label className="content-ops-field">
            <span>Prompt</span>
            <input
              type="text"
              value={imagePrompt}
              disabled={generating || !workspaceId}
              onChange={(event) => setImagePrompt(event.target.value)}
            />
          </label>
          <label className="content-ops-field">
            <span>Count</span>
            <input
              type="number"
              min={1}
              max={4}
              value={imageCount}
              disabled={generating || !workspaceId}
              onChange={(event) => setImageCount(Number(event.target.value) || 1)}
            />
          </label>
          <label className="content-ops-field">
            <span>Agent (optional)</span>
            <select
              value={imageAgentId}
              disabled={generating || !workspaceId}
              onChange={(event) => setImageAgentId(event.target.value)}
            >
              <option value="">No agent</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={generating || !workspaceId}>
            {generating ? 'Queuing…' : 'Queue image job'}
          </button>
        </form>
      </section>
    </div>
  );
};

export default RegionalAgentsPage;

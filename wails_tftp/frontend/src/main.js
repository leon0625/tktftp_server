import './style.css';
import appIcon from './assets/images/appicon.png';
import {
  BrowseLocalFile,
  BrowseRoot,
  ChooseSaveFile,
  ClearCompleted,
  GetInitialState,
  StartClientTransfer,
  StartServer,
  StopServer,
} from '../wailsjs/go/main/App';
import {
  EventsOn,
  Quit,
  WindowIsMaximised,
  WindowMinimise,
  WindowToggleMaximise,
} from '../wailsjs/runtime/runtime';

const app = document.querySelector('#app');

let state = {
  rootDirectory: '',
  rootHistory: [],
  listenIP: '0.0.0.0',
  serverIP: '0.0.0.0',
  port: 69,
  serverStatus: 'Stopped',
  transfers: [],
  clientTransfer: null,
  counts: { total: 0, completed: 0, inProgress: 0, failed: 0 },
};

const trashIcon = `
  <svg class="icon-svg trash-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 7h16" />
    <path d="M9 7V4h6v3" />
    <path d="M7 7l1 13h8l1-13" />
    <path d="M10 11v6" />
    <path d="M14 11v6" />
  </svg>
`;

const pcIcon = `
  <svg class="icon-svg pc-icon" viewBox="0 0 24 24" aria-hidden="true">
    <rect x="4" y="5" width="16" height="11" rx="1.6" />
    <path d="M10 19h4" />
    <path d="M12 16v3" />
    <path d="M7 16h10" />
  </svg>
`;

app.innerHTML = `
  <main class="window">
    <header class="titlebar">
      <div class="titlebar-brand">
        <img src="${appIcon}" alt="" />
        <span>TFTP Tool</span>
      </div>
      <div class="titlebar-drag"></div>
      <div class="window-controls">
        <button id="window-minimise" class="window-button" title="Minimize">−</button>
        <button id="window-maximise" class="window-button" title="Maximize">□</button>
        <button id="window-close" class="window-button close" title="Close">×</button>
      </div>
    </header>
    <section class="content">
      <div class="main-grid">
        <section class="panel server">
          <div class="panel-title-row">
            <div class="panel-title">
              <div class="circle-icon">▤</div>
              <span>TFTP Server</span>
            </div>
            <div class="top-running">Status: <span id="server-status">Stopped</span></div>
          </div>

          <fieldset>
            <legend>Server Configuration</legend>
            <div class="config-row">
              <label class="label" for="root-dir">Root Directory:</label>
              <div class="root-picker">
                <input id="root-dir" autocomplete="off" />
                <button id="root-history-toggle" class="root-history-toggle" title="Show history">⌄</button>
                <div id="root-history-menu" class="root-history-menu"></div>
              </div>
              <button id="browse-root">Browse...</button>
              <button id="start-server" class="server-toggle start-toggle">Start</button>
              <button id="stop-server" class="server-toggle stop-toggle">Stop</button>
            </div>
          </fieldset>

          <fieldset class="table-field">
            <legend>Transfer List</legend>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th class="file-col">File Name</th>
                    <th class="status-col">Status</th>
                    <th class="progress-col">Progress</th>
                    <th class="peer-col">Peer</th>
                    <th class="size-col">Size</th>
                    <th class="speed-col">Speed</th>
                  </tr>
                </thead>
                <tbody id="transfer-body"></tbody>
              </table>
            </div>

            <div class="server-actions">
              <button id="clear-history" class="clear-btn">${trashIcon}Clear History</button>
            </div>
          </fieldset>
        </section>

        <section class="panel client">
          <div class="panel-title">
            <div class="circle-icon">${pcIcon}</div>
            <span>TFTP Client</span>
          </div>

          <div class="client-row">
            <label class="label" for="server-ip">Server IP:</label>
            <input id="server-ip" />
          </div>
          <div class="client-row">
            <label class="label" for="port">Port:</label>
            <input id="port" class="port-input" />
          </div>
          <div class="client-row file">
            <label class="label" for="local-file">Local File:</label>
            <input id="local-file" />
            <button id="browse-local">Browse...</button>
          </div>
          <div class="client-row">
            <label class="label" for="remote-file">Remote File:</label>
            <input id="remote-file" />
          </div>

          <div class="client-buttons">
            <button id="get-file" class="transfer-btn"><span>⇩</span>Get</button>
            <button id="put-file" class="transfer-btn"><span>⇧</span>Put</button>
          </div>

          <div class="progress-title">Progress</div>
          <div class="progress">
            <div id="client-progress-bar" class="bar"></div>
            <div id="client-progress-text" class="pct">0%</div>
          </div>

          <div class="detail-grid">
            <div>Status:</div><div id="client-status" class="active">Idle</div>
            <div>Mode:</div><div>octet</div>
            <div>Transferred:</div><div id="client-transferred">0 B / 0 B</div>
            <div>Speed:</div><div id="client-speed">0 B/s</div>
            <div>Elapsed Time:</div><div id="client-elapsed">00:00:00</div>
            <div>Estimated Time:</div><div id="client-estimated">00:00:00</div>
          </div>

        </section>
      </div>

      <footer class="footer">
        <div class="footer-item"><span class="footer-icon">◎</span><span>Server IP:</span><span id="footer-ip">0.0.0.0</span></div>
        <div class="footer-item"><span class="footer-icon">▣</span><span>Port:</span><span id="footer-port">69</span></div>
        <div class="footer-item"><span class="footer-icon">↔</span><span>Total Transfers:</span><span id="footer-total">0</span></div>
        <div class="footer-item"><span class="footer-icon ok">✓</span><span>Completed:</span><span id="footer-completed">0</span></div>
        <div class="footer-item"><span class="footer-icon">○</span><span class="blue-text">In Progress:</span><span id="footer-progress">0</span></div>
        <div class="footer-item"><span class="footer-icon fail">×</span><span>Failed:</span><span id="footer-failed">0</span></div>
      </footer>
    </section>
  </main>
  <div id="toast" class="toast"></div>
`;

const $ = (selector) => document.querySelector(selector);

const rootDir = $('#root-dir');
const serverIP = $('#server-ip');
const port = $('#port');
const localFile = $('#local-file');
const remoteFile = $('#remote-file');
const transferBody = $('#transfer-body');
const rootHistoryMenu = $('#root-history-menu');
const toast = $('#toast');
const maximiseButton = $('#window-maximise');

$('#window-minimise').addEventListener('click', () => WindowMinimise());
maximiseButton.addEventListener('click', () => toggleMaximise());
$('#window-close').addEventListener('click', () => Quit());
$('.titlebar').addEventListener('dblclick', (event) => {
  if (event.target.closest('.window-controls')) return;
  toggleMaximise();
});

$('#browse-root').addEventListener('click', async () => {
  const dir = await BrowseRoot();
  if (!dir) return;
  rootDir.value = dir;
  syncInputTitles();
  await applyRootDirectory();
});

$('#clear-history').addEventListener('click', () => ClearCompleted().catch(showError));
$('#start-server').addEventListener('click', () => startServer().catch(showError));
$('#stop-server').addEventListener('click', () => StopServer().catch(showError));
$('#root-history-toggle').addEventListener('click', (event) => {
  event.preventDefault();
  event.stopPropagation();
  toggleRootHistory();
});

$('#browse-local').addEventListener('click', async () => {
  const file = await BrowseLocalFile();
  if (!file) return;
  localFile.value = file;
  syncInputTitles();
});

$('#get-file').addEventListener('click', async () => {
  if (!remoteFile.value.trim()) {
    showError('Remote file is required.');
    return;
  }
  let target = localFile.value.trim();
  if (!target) {
    target = await ChooseSaveFile(remoteFile.value.trim().split(/[\\/]/).pop());
    if (!target) return;
    localFile.value = target;
  }
  await startTransfer('get');
});

$('#put-file').addEventListener('click', () => startTransfer('put'));

rootDir.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') applyRootDirectory();
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    showRootHistory();
  }
});
rootDir.addEventListener('change', applyRootDirectory);
rootDir.addEventListener('input', syncInputTitles);
rootDir.addEventListener('blur', () => {
  window.setTimeout(() => {
    if (!document.activeElement?.closest?.('.root-picker')) applyRootDirectory();
  }, 100);
});
rootDir.addEventListener('focus', () => {
  if ((state.rootHistory || []).length > 1) showRootHistory();
});
document.addEventListener('click', (event) => {
  if (!event.target.closest('.root-picker')) hideRootHistory();
});
[serverIP, port, localFile, remoteFile].forEach((input) => {
  input.addEventListener('input', syncInputTitles);
});

async function applyRootDirectory() {
  if (state.serverStatus !== 'Running' && state.serverStatus !== 'Starting') return;
  await startServer();
}

async function startServer() {
  const dir = rootDir.value.trim();
  if (!dir) {
    showError('Root directory is required.');
    return;
  }
  if (dir === state.rootDirectory && state.serverStatus === 'Running') return;
  try {
    await StartServer(dir);
  } catch (error) {
    showError(error);
  }
}

async function startTransfer(action) {
  const local = localFile.value.trim();
  let remote = remoteFile.value.trim();
  if (action === 'put' && !remote && local) {
    remote = local.split(/[\\/]/).pop();
  }
  if (action === 'get' && !remote) {
    showError('Remote file is required for Get.');
    return;
  }
  const request = {
    action,
    host: serverIP.value.trim(),
    port: Number.parseInt(port.value, 10) || 69,
    localFile: local,
    remoteFile: remote,
  };
  if (!request.host || !request.localFile) {
    showError('Server IP and local file are required.');
    return;
  }
  try {
    await StartClientTransfer(request);
  } catch (error) {
    showError(error);
  }
}

function render(nextState) {
  state = nextState || state;
  if (document.activeElement !== rootDir) {
    rootDir.value = state.rootDirectory || '';
  }
  renderRootHistory();
  serverIP.value = serverIP.value || state.serverIP || '127.0.0.1';
  port.value = port.value || String(state.port || 69);
  syncInputTitles();
  $('#server-status').textContent = state.serverStatus || 'Stopped';
  $('#server-status').className = statusClass(state.serverStatus);
  const isRunning = state.serverStatus === 'Running' || state.serverStatus === 'Starting';
  $('#start-server').disabled = isRunning;
  $('#stop-server').disabled = !isRunning;

  transferBody.innerHTML = '';
  const transfers = state.transfers || [];
  if (transfers.length === 0) {
    transferBody.innerHTML = `<tr class="empty-row"><td colspan="6">No transfers yet</td></tr>`;
  } else {
    for (const record of transfers) {
      const percent = progressPercent(record);
      const status = displayStatus(record);
      const peer = peerHost(record.peer || '');
      const size = formatBytes(record.bytesTotal || record.bytesDone);
      const speed = formatSpeed(record);
      const row = document.createElement('tr');
      row.innerHTML = `
        <td title="${escapeHtml(record.fileName || '')}">${escapeHtml(baseName(record.fileName || ''))}</td>
        <td class="${statusClass(record.status)}" title="${escapeHtml(status)}">${escapeHtml(status)}</td>
        <td title="${percent}%">
          <div class="progress-cell">
            <div class="mini-progress">
              <div class="bar" style="width:${percent}%"></div>
              <span>${percent}%</span>
            </div>
          </div>
        </td>
        <td title="${escapeHtml(record.peer || '')}">${escapeHtml(peer)}</td>
        <td title="${escapeHtml(size)}">${escapeHtml(size)}</td>
        <td title="${escapeHtml(speed)}">${escapeHtml(speed)}</td>
      `;
      transferBody.appendChild(row);
    }
  }

  renderClientDetails(state.clientTransfer);
  renderFooter();
}

function renderRootHistory() {
  rootHistoryMenu.innerHTML = '';
  const history = state.rootHistory || [];
  if (history.length === 0) {
    rootHistoryMenu.innerHTML = `<div class="root-history-empty">No history</div>`;
    return;
  }
  for (const item of history) {
    const option = document.createElement('button');
    option.type = 'button';
    option.className = 'root-history-item';
    option.textContent = item;
    option.title = item;
    option.addEventListener('click', async () => {
      rootDir.value = item;
      syncInputTitles();
      hideRootHistory();
      await applyRootDirectory();
    });
    rootHistoryMenu.appendChild(option);
  }
}

function toggleRootHistory() {
  if (rootHistoryMenu.classList.contains('show')) {
    hideRootHistory();
  } else {
    showRootHistory();
  }
}

function showRootHistory() {
  renderRootHistory();
  rootHistoryMenu.classList.add('show');
}

function hideRootHistory() {
  rootHistoryMenu.classList.remove('show');
}

function renderClientDetails(record) {
  if (!record) {
    $('#client-status').textContent = 'Idle';
    $('#client-progress-bar').style.width = '0%';
    $('#client-progress-text').textContent = '0%';
    $('#client-transferred').textContent = '0 B / 0 B';
    $('#client-speed').textContent = '0 B/s';
    $('#client-elapsed').textContent = '00:00:00';
    $('#client-estimated').textContent = '00:00:00';
    $('#client-status').title = 'Idle';
    $('#client-transferred').title = '0 B / 0 B';
    $('#client-speed').title = '0 B/s';
    $('#client-elapsed').title = '00:00:00';
    $('#client-estimated').title = '00:00:00';
    return;
  }
  const percent = progressPercent(record);
  const status = displayStatus(record);
  renderClientStatus(record, status, percent);
  $('#client-status').title = status;
  $('#client-status').className = `active ${statusClass(record.status)}`;
  $('#client-progress-bar').style.width = `${percent}%`;
  $('#client-progress-text').textContent = `${percent}%`;
  setTextAndTitle($('#client-transferred'), `${formatBytes(record.bytesDone)} / ${formatBytes(record.bytesTotal)}`);
  setTextAndTitle($('#client-speed'), formatSpeed(record));
  setTextAndTitle($('#client-elapsed'), formatDuration(elapsedSeconds(record)));
  setTextAndTitle($('#client-estimated'), estimateRemaining(record));
}

function renderFooter() {
  $('#footer-ip').textContent = state.listenIP || '0.0.0.0';
  $('#footer-port').textContent = state.port || 69;
  $('#footer-total').textContent = state.counts?.total || 0;
  $('#footer-completed').textContent = state.counts?.completed || 0;
  $('#footer-progress').textContent = state.counts?.inProgress || 0;
  $('#footer-failed').textContent = state.counts?.failed || 0;
}

function progressPercent(record) {
  if (!record) return 0;
  if (record.status === 'Completed') return 100;
  if (!record.bytesTotal) return record.bytesDone ? 1 : 0;
  return Math.max(0, Math.min(100, Math.floor((record.bytesDone / record.bytesTotal) * 100)));
}

function elapsedSeconds(record) {
  if (!record?.startedAt) return 0;
  const end = record.endedAt || Date.now();
  return Math.max(0, Math.floor((end - record.startedAt) / 1000));
}

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function estimateRemaining(record) {
  if (!record || !record.bytesDone || !record.bytesTotal || record.status === 'Completed') {
    return '00:00:00';
  }
  const elapsed = Math.max(1, elapsedSeconds(record));
  const rate = record.bytesDone / elapsed;
  if (!rate) return '00:00:00';
  return formatDuration(Math.ceil((record.bytesTotal - record.bytesDone) / rate));
}

function formatBytes(value) {
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = Number(value || 0);
  for (const unit of units) {
    if (size < 1024 || unit === 'GB') {
      return unit === 'B' ? `${size | 0} B` : `${size.toFixed(2)} ${unit}`;
    }
    size /= 1024;
  }
  return '0 B';
}

function formatSpeed(record) {
  if (!record || !record.bytesDone) return '0 B/s';
  const elapsed = Math.max(1, elapsedSeconds(record));
  return `${formatBytes(record.bytesDone / elapsed)}/s`;
}

function statusClass(status) {
  if (status === 'Completed' || status === 'Running') return 'green-text';
  if (status === 'Failed' || status === 'Stopped') return 'red-text';
  return 'blue-text';
}

function renderClientStatus(record, status, percent) {
  const statusElement = $('#client-status');
  if (isTransferInProgress(record.status)) {
    statusElement.innerHTML = `
      <div class="client-status-progress">
        <span>${escapeHtml(status)}</span>
        <div class="client-status-bar">
          <div class="bar" style="width:${percent}%"></div>
          <span>${percent}%</span>
        </div>
      </div>
    `;
    return;
  }
  statusElement.textContent = status;
}

function isTransferInProgress(status) {
  return status === 'Sending' || status === 'Receiving' || status === 'Transferring';
}

function displayStatus(record) {
  if (!record) return 'Idle';
  const status = record.status || 'Idle';
  if (status === 'Completed') {
    return isReceiveDirection(record.direction) ? 'Recv Done' : 'Send Done';
  }
  if (status === 'Failed' && record.error) {
    return `${status}: ${record.error}`;
  }
  return status;
}

function isReceiveDirection(direction) {
  const value = String(direction || '').toLowerCase();
  return value === 'receiving' || value === 'recv' || value === 'get';
}

function peerHost(peer) {
  const value = String(peer || '').trim();
  if (!value) return '';
  if (value.startsWith('[')) {
    const end = value.indexOf(']');
    return end > 0 ? value.slice(1, end) : value;
  }
  const lastColon = value.lastIndexOf(':');
  if (lastColon > -1 && value.indexOf(':') === lastColon) {
    return value.slice(0, lastColon);
  }
  return value;
}

function baseName(path) {
  return path.split(/[\\/]/).pop() || path;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function setTextAndTitle(element, value) {
  element.textContent = value;
  element.title = value;
}

function syncInputTitles() {
  [rootDir, serverIP, port, localFile, remoteFile].forEach((input) => {
    input.title = input.value || '';
  });
}

let toastTimer;
function showError(error) {
  const message = typeof error === 'string' ? error : error?.message || String(error);
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}

EventsOn('state', render);
EventsOn('app-error', showError);

GetInitialState().then(render).catch(showError);
syncMaximiseButton();

async function toggleMaximise() {
  WindowToggleMaximise();
  window.setTimeout(syncMaximiseButton, 80);
}

async function syncMaximiseButton() {
  try {
    const maximised = await WindowIsMaximised();
    maximiseButton.textContent = maximised ? '❐' : '□';
    maximiseButton.title = maximised ? 'Restore' : 'Maximize';
  } catch (_error) {
    maximiseButton.textContent = '□';
  }
}

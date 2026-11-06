const modelList = document.getElementById('model-list');
const newModelBtn = document.getElementById('new-model-btn');
const newModelDialog = document.getElementById('new-model-dialog');
const newModelForm = document.getElementById('new-model-form');
const cancelNewModel = document.getElementById('cancel-new-model');
const emptyState = document.getElementById('empty-state');
const modelView = document.getElementById('model-view');
const modelNameEl = document.getElementById('model-name');
const referenceImg = document.getElementById('reference-img');
const gallery = document.getElementById('gallery');
const generateForm = document.getElementById('generate-form');
const promptInput = document.getElementById('prompt-input');
const statusEl = document.getElementById('status');

let currentSlug = null;

async function loadModels() {
  const models = await fetch('/models').then((r) => r.json());
  modelList.innerHTML = '';
  for (const m of models) {
    const li = document.createElement('li');
    li.textContent = m.name;
    li.className = m.slug === currentSlug ? 'active' : '';
    li.addEventListener('click', () => selectModel(m.slug));
    modelList.appendChild(li);
  }
}

async function selectModel(slug) {
  currentSlug = slug;
  const model = await fetch(`/models/${slug}`).then((r) => r.json());
  emptyState.hidden = true;
  modelView.hidden = false;
  modelNameEl.textContent = model.name;
  referenceImg.src = `/data/models/${slug}/reference.png?t=${Date.now()}`;
  gallery.innerHTML = '';
  for (const filename of model.generations) {
    addGalleryImage(slug, filename);
  }
  loadModels();
}

function addGalleryImage(slug, filename) {
  const img = document.createElement('img');
  img.src = `/data/models/${slug}/generations/${filename}`;
  gallery.appendChild(img);
}

newModelBtn.addEventListener('click', () => newModelDialog.showModal());
cancelNewModel.addEventListener('click', () => newModelDialog.close());

newModelForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('new-model-name').value;
  const prompt = document.getElementById('new-model-prompt').value;
  newModelDialog.close();
  statusEl.textContent = 'Creating reference image... (cold start can take a minute or two)';

  const resp = await fetch('/models', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, prompt }),
  });

  if (!resp.ok) {
    statusEl.textContent = 'Failed to create model: ' + (await resp.text());
    return;
  }

  statusEl.textContent = '';
  const model = await resp.json();
  newModelForm.reset();
  await loadModels();
  selectModel(model.slug);
});

generateForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!currentSlug) return;
  const prompt = promptInput.value;
  statusEl.textContent = 'Generating... (cold start can take a minute or two)';

  const resp = await fetch(`/models/${currentSlug}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  });

  if (!resp.ok) {
    statusEl.textContent = 'Failed to generate: ' + (await resp.text());
    return;
  }

  statusEl.textContent = '';
  const { filename } = await resp.json();
  addGalleryImage(currentSlug, filename);
  promptInput.value = '';
});

loadModels();

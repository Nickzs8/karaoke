/**
 * Controlador da Página 1: Preparação de Músicas e Catálogo (Toggl Track Style)
 */

import { api } from "./api.js?v=2.0.0";

// Elementos do DOM
const dom = {
  // Abas de Preparo
  tabButtons: document.querySelectorAll(".tab-btn"),
  tabContents: document.querySelectorAll(".tab-content"),

  // Formulário YouTube
  ytForm: document.getElementById("ytForm"),
  ytQueryInput: document.getElementById("ytQueryInput"),
  ytTitleInput: document.getElementById("ytTitleInput"),
  ytArtistInput: document.getElementById("ytArtistInput"),
  ytSubmitBtn: document.getElementById("ytSubmitBtn"),

  // Formulário Upload
  fileForm: document.getElementById("fileForm"),
  dropzone: document.getElementById("dropzone"),
  audioFileInput: document.getElementById("audioFileInput"),
  dropzoneText: document.getElementById("dropzoneText"),
  fileTitleInput: document.getElementById("fileTitleInput"),
  fileArtistInput: document.getElementById("fileArtistInput"),
  fileSubmitBtn: document.getElementById("fileSubmitBtn"),

  // Indicador de Carregamento
  loadingBox: document.getElementById("loadingBox"),
  loadingText: document.getElementById("loadingText"),
  loadingStep: document.getElementById("loadingStep"),

  // Catálogo
  songsList: document.getElementById("songsList"),
  songsCount: document.getElementById("songsCount"),
};

// Inicialização
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupForms();
  loadCatalog();
});

// ==========================================================================
// 1. Gestão de Abas e Formulários
// ==========================================================================

function setupTabs() {
  dom.tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      dom.tabButtons.forEach((b) => b.classList.remove("active"));
      dom.tabContents.forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      const targetEl = document.getElementById(target);
      if (targetEl) targetEl.classList.add("active");
    });
  });
}

function setupForms() {
  // Envio via URL/Busca do YouTube
  dom.ytForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = dom.ytQueryInput.value.trim();
    if (!query) return;

    showLoading("Processando música...", "1/3 Baixando áudio original...");
    dom.ytSubmitBtn.disabled = true;

    try {
      updateLoadingStep("2/3 Separando faixas com inteligência artificial...");
      const song = await api.prepareSongByUrl(
        query,
        dom.ytTitleInput.value,
        dom.ytArtistInput.value
      );
      updateLoadingStep("3/3 Sincronizando letra...");

      // Redireciona diretamente para o palco de performance
      window.location.href = `/sing?id=${encodeURIComponent(song.id)}`;
    } catch (err) {
      alert(`Erro: ${err.message}`);
      dom.ytSubmitBtn.disabled = false;
      hideLoading();
    }
  });

  // Dropzone de Arquivo
  dom.dropzone.addEventListener("click", () => dom.audioFileInput.click());
  dom.dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dom.dropzone.classList.add("dragover");
  });
  dom.dropzone.addEventListener("dragleave", () =>
    dom.dropzone.classList.remove("dragover")
  );
  dom.dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dom.dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
      dom.audioFileInput.files = e.dataTransfer.files;
      handleFileSelected();
    }
  });
  dom.audioFileInput.addEventListener("change", handleFileSelected);

  // Envio via Upload de Arquivo
  dom.fileForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = dom.audioFileInput.files[0];
    if (!file) {
      alert("Por favor selecione um arquivo de áudio.");
      return;
    }

    showLoading("Processando arquivo...", "Separando faixas instrumentais...");
    dom.fileSubmitBtn.disabled = true;

    try {
      const song = await api.prepareSongByFile(
        file,
        dom.fileTitleInput.value,
        dom.fileArtistInput.value
      );

      // Redireciona diretamente para o palco de performance
      window.location.href = `/sing?id=${encodeURIComponent(song.id)}`;
    } catch (err) {
      alert(`Erro: ${err.message}`);
      dom.fileSubmitBtn.disabled = false;
      hideLoading();
    }
  });
}

function handleFileSelected() {
  const file = dom.audioFileInput.files[0];
  if (file) {
    dom.dropzoneText.innerHTML = `<strong>Arquivo selecionado:</strong><br>${escapeHtml(file.name)} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
  }
}

function showLoading(title, step) {
  dom.loadingText.textContent = title;
  dom.loadingStep.textContent = step;
  dom.loadingBox.style.display = "block";
}

function updateLoadingStep(step) {
  dom.loadingStep.textContent = step;
}

function hideLoading() {
  dom.loadingBox.style.display = "none";
}

// ==========================================================================
// 2. Catálogo de Músicas
// ==========================================================================

async function loadCatalog() {
  try {
    const songs = await api.getSongs(true);
    dom.songsCount.textContent = `${songs.length} ${songs.length === 1 ? "faixa" : "faixas"}`;

    if (songs.length === 0) {
      dom.songsList.innerHTML = `<div class="empty-state">Nenhuma faixa pronta no catálogo ainda.<br>Prepare uma música no painel ao lado para começar!</div>`;
      return;
    }

    dom.songsList.innerHTML = "";
    songs.forEach((song, index) => {
      const item = document.createElement("div");
      item.className = "song-row";

      const minutes = Math.floor(song.duration / 60);
      const seconds = Math.floor(song.duration % 60)
        .toString()
        .padStart(2, "0");

      item.innerHTML = `
        <div class="col-num">${index + 1}</div>
        <div class="col-track">
          <div class="song-title">${escapeHtml(song.title)}</div>
          <div class="song-artist">${escapeHtml(song.artist)}</div>
        </div>
        <div class="col-duration">${minutes}:${seconds}</div>
        <div class="col-action">
          <button class="btn-sing" data-id="${song.id}">
            Cantar
          </button>
        </div>
      `;

      item.querySelector(".btn-sing").addEventListener("click", () => {
        window.location.href = `/sing?id=${encodeURIComponent(song.id)}`;
      });

      dom.songsList.appendChild(item);
    });
  } catch (err) {
    console.error("Falha ao listar catálogo:", err);
    dom.songsList.innerHTML = `<div class="empty-state">Erro ao carregar catálogo: ${escapeHtml(err.message)}</div>`;
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[m]));
}

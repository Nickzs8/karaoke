/**
 * Controlador Principal da Interface do Usuário (UI Orchestrator)
 */

import { api } from "./api.js";
import { AudioPlayer } from "./audio-player.js";
import { VoiceRecorder } from "./recorder.js";

// Instâncias Globais
const player = new AudioPlayer();
const recorder = new VoiceRecorder();

let currentSong = null;
let currentLyrics = [];
let isEvaluating = false;

// Elementos do DOM
const dom = {
  // Status do Microfone
  micBadge: document.getElementById("micBadge"),
  micStatusText: document.getElementById("micStatusText"),

  // Abas de Preparo
  tabButtons: document.querySelectorAll(".tab-btn"),
  tabContents: document.querySelectorAll(".tab-content"),

  // Formulário YouTube
  ytForm: document.getElementById("ytForm"),
  ytQueryInput: document.getElementById("ytQueryInput"),
  ytTitleInput: document.getElementById("ytTitleInput"),
  ytArtistInput: document.getElementById("ytArtistInput"),
  ytSubmitBtn: document.getElementById("ytSubmitBtn"),

  // Formulário Upload de Arquivo
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

  // Palco do Karaokê
  stageContainer: document.getElementById("stageContainer"),
  currentSongTitle: document.getElementById("currentSongTitle"),
  currentSongArtist: document.getElementById("currentSongArtist"),
  btnChangeSong: document.getElementById("btnChangeSong"),
  lyricsBox: document.getElementById("lyricsBox"),

  // Controles do Player
  currentTimeLabel: document.getElementById("currentTimeLabel"),
  totalTimeLabel: document.getElementById("totalTimeLabel"),
  progressBarContainer: document.getElementById("progressBarContainer"),
  progressBarFill: document.getElementById("progressBarFill"),
  btnPlayPause: document.getElementById("btnPlayPause"),
  playIcon: document.getElementById("playIcon"),
  btnRecordMic: document.getElementById("btnRecordMic"),
  recBtnLabel: document.getElementById("recBtnLabel"),
  btnFinishSinging: document.getElementById("btnFinishSinging"),

  // Modal de Pontuação
  modalOverlay: document.getElementById("modalOverlay"),
  scoreNumber: document.getElementById("scoreNumber"),
  scoreRating: document.getElementById("scoreRating"),
  pitchScoreValue: document.getElementById("pitchScoreValue"),
  timingScoreValue: document.getElementById("timingScoreValue"),
  centsErrorValue: document.getElementById("centsErrorValue"),
  timingDevValue: document.getElementById("timingDevValue"),
  pitchCanvas: document.getElementById("pitchChartCanvas"),
  btnRetryModal: document.getElementById("btnRetryModal"),
  btnCloseModal: document.getElementById("btnCloseModal"),
};

// Inicialização
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupForms();
  setupPlayerCallbacks();
  setupRecorderCallbacks();
  setupModalEvents();
  loadCatalog();
});

// ==========================================================================
// 1. Gestão de Abas e Formulários de Preparo
// ==========================================================================

function setupTabs() {
  dom.tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      dom.tabButtons.forEach((b) => b.classList.remove("active"));
      dom.tabContents.forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      document.getElementById(target).classList.add("active");
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
      updateLoadingStep("2/3 Separando voz e instrumental...");
      const song = await api.prepareSongByUrl(
        query,
        dom.ytTitleInput.value,
        dom.ytArtistInput.value
      );
      updateLoadingStep("3/3 Finalizando e sincronizando letra...");

      dom.ytQueryInput.value = "";
      dom.ytTitleInput.value = "";
      dom.ytArtistInput.value = "";

      await loadCatalog();
      selectSong(song);
    } catch (err) {
      alert(`Erro: ${err.message}`);
    } finally {
      hideLoading();
      dom.ytSubmitBtn.disabled = false;
    }
  });

  // Dropzone de Arquivo
  dom.dropzone.addEventListener("click", () => dom.audioFileInput.click());
  dom.dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dom.dropzone.classList.add("dragover");
  });
  dom.dropzone.addEventListener("dragleave", () => dom.dropzone.classList.remove("dragover"));
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

      dom.fileForm.reset();
      dom.dropzoneText.textContent = "Arraste um arquivo .mp3 ou .wav aqui ou clique";

      await loadCatalog();
      selectSong(song);
    } catch (err) {
      alert(`Erro: ${err.message}`);
    } finally {
      hideLoading();
      dom.fileSubmitBtn.disabled = false;
    }
  });
}

function handleFileSelected() {
  const file = dom.audioFileInput.files[0];
  if (file) {
    dom.dropzoneText.innerHTML = `<strong>Arquivo selecionado:</strong><br>${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
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
    dom.songsCount.textContent = `(${songs.length})`;

    if (songs.length === 0) {
      dom.songsList.innerHTML = `<div class="empty-state">Nenhuma música pronta no catálogo ainda.<br>Prepare uma acima para começar!</div>`;
      return;
    }

    dom.songsList.innerHTML = "";
    songs.forEach((song) => {
      const item = document.createElement("div");
      item.className = "song-item";
      if (currentSong && currentSong.id === song.id) item.classList.add("active");

      const minutes = Math.floor(song.duration / 60);
      const seconds = Math.floor(song.duration % 60).toString().padStart(2, "0");

      item.innerHTML = `
        <div class="song-info">
          <div class="song-name">${escapeHtml(song.title)}</div>
          <div class="song-meta">
            <span>${escapeHtml(song.artist)}</span>
            <span>${minutes}:${seconds}</span>
          </div>
        </div>
        <button class="btn-sing" data-id="${song.id}">
          Cantar
        </button>
      `;

      item.querySelector(".btn-sing").addEventListener("click", () => selectSong(song));
      dom.songsList.appendChild(item);
    });
  } catch (err) {
    console.error("Falha ao listar catálogo:", err);
  }
}

// ==========================================================================
// 3. Palco do Karaokê (Player e Letras Sincronizadas)
// ==========================================================================

async function selectSong(song) {
  currentSong = song;
  dom.currentSongTitle.textContent = song.title;
  dom.currentSongArtist.textContent = song.artist;

  // Carrega letra sincronizada
  try {
    const lyricsData = await api.getLyrics(song.id);
    currentLyrics = lyricsData.lines || [];
  } catch {
    currentLyrics = [];
  }

  renderLyrics(currentLyrics);

  // Inicializa o player com a faixa instrumental
  if (song.instrumental_url) {
    player.load(song.instrumental_url, currentLyrics);
  }

  // Ativa a visão do palco e rola suavemente
  dom.stageContainer.classList.add("active");
  dom.stageContainer.scrollIntoView({ behavior: "smooth" });

  loadCatalog();
}

function renderLyrics(lines) {
  dom.lyricsBox.innerHTML = "";

  if (!lines || lines.length === 0) {
    dom.lyricsBox.innerHTML = `
      <div style="padding: 60px 20px; color: var(--text-dim);">
        <p style="font-size: 1.2rem; margin-bottom: 8px;">Letra sincronizada não disponível para esta faixa.</p>
        <p style="font-size: 0.9rem;">Siga o playback instrumental e cante livremente!</p>
      </div>
    `;
    return;
  }

  lines.forEach((line, index) => {
    const div = document.createElement("div");
    div.className = "lyric-line";
    div.id = `line-${index}`;
    div.textContent = line.text;
    dom.lyricsBox.appendChild(div);
  });
}

function setupPlayerCallbacks() {
  // Atualização da timeline
  player.onTimeUpdate = (currentTime, duration, percent) => {
    dom.currentTimeLabel.textContent = formatTime(currentTime);
    dom.totalTimeLabel.textContent = formatTime(duration);
    dom.progressBarFill.style.width = `${percent}%`;
  };

  // Sincronização e rolagem automática da letra
  player.onLineChange = (line, index) => {
    document.querySelectorAll(".lyric-line").forEach((el, i) => {
      el.classList.remove("active");
      if (i < index) el.classList.add("past");
      else el.classList.remove("past");
    });

    if (index >= 0) {
      const activeEl = document.getElementById(`line-${index}`);
      if (activeEl) {
        activeEl.classList.add("active");
        // Centraliza a linha ativa no painel de letras
        activeEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  };

  player.onPlay = () => {
    dom.playIcon.textContent = "❚❚";
  };

  player.onPause = () => {
    dom.playIcon.textContent = "▶";
  };

  // Quando a música termina naturalmente
  player.onEnded = async () => {
    dom.playIcon.textContent = "▶";
    if (recorder.isRecording) {
      await finishPerformanceAndScore();
    }
  };

  // Botão Play/Pause
  dom.btnPlayPause.addEventListener("click", () => {
    if (player.isPlaying()) player.pause();
    else player.play();
  });

  // Clique na barra de progresso para seek
  dom.progressBarContainer.addEventListener("click", (e) => {
    const rect = dom.progressBarContainer.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percent = (clickX / rect.width) * 100;
    player.seekPercent(percent);
  });

  // Botão de Trocar Música
  dom.btnChangeSong.addEventListener("click", () => {
    player.pause();
    if (recorder.isRecording) recorder.stop();
    dom.stageContainer.classList.remove("active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

// ==========================================================================
// 4. Módulo de Gravação do Microfone (MediaRecorder)
// ==========================================================================

function setupRecorderCallbacks() {
  // Inicia ou pausa a gravação do microfone
  dom.btnRecordMic.addEventListener("click", async () => {
    try {
      if (!recorder.isRecording) {
        await recorder.start();
        dom.btnRecordMic.classList.add("recording");
        if (dom.recBtnLabel) dom.recBtnLabel.textContent = "Gravando...";
        dom.micBadge.classList.add("active");
        dom.micStatusText.textContent = "Microfone Ativo";

        // Dá play na música sincronizada
        player.play();
      } else {
        await finishPerformanceAndScore();
      }
    } catch (err) {
      alert(`Permissão de microfone necessária: ${err.message}`);
    }
  });

  dom.btnFinishSinging.addEventListener("click", async () => {
    await finishPerformanceAndScore();
  });
}

async function finishPerformanceAndScore() {
  if (isEvaluating) return;
  isEvaluating = true;

  player.pause();

  dom.btnRecordMic.classList.remove("recording");
  if (dom.recBtnLabel) dom.recBtnLabel.textContent = "Gravar Voz";
  dom.micBadge.classList.remove("active");
  dom.micStatusText.textContent = "Microfone Pronto";

  showLoading("Avaliando performance...", "Analisando afinação e ritmo...");

  try {
    const audioBlob = await recorder.stop();

    if (!audioBlob || audioBlob.size === 0) {
      alert("Nenhum áudio foi gravado. Cante enquanto o instrumental toca!");
      return;
    }

    // Envia gravação para a API
    const scoreResult = await api.evaluatePerformance(currentSong.id, audioBlob);
    showScoreModal(scoreResult);
  } catch (err) {
    alert(`Erro na avaliação: ${err.message}`);
  } finally {
    hideLoading();
    isEvaluating = false;
  }
}

// ==========================================================================
// 5. Modal de Pontuação e Renderizador do Gráfico
// ==========================================================================

function setupModalEvents() {
  dom.btnCloseModal.addEventListener("click", () => {
    dom.modalOverlay.classList.remove("active");
  });

  dom.btnRetryModal.addEventListener("click", () => {
    dom.modalOverlay.classList.remove("active");
    player.seek(0);
    player.play();
    recorder.start();
    dom.btnRecordMic.classList.add("recording");
    if (dom.recBtnLabel) dom.recBtnLabel.textContent = "Gravando...";
  });
}

function showScoreModal(score) {
  dom.scoreNumber.textContent = Math.round(score.total_score);
  dom.pitchScoreValue.textContent = `${score.pitch_score.toFixed(1)}%`;
  dom.timingScoreValue.textContent = `${score.timing_score.toFixed(1)}%`;

  // Detalhes extras
  const meanCents = score.details?.mean_cents_error ?? 0;
  const timingDev = score.details?.mean_timing_deviation_seconds ?? 0;

  dom.centsErrorValue.textContent = `${meanCents.toFixed(1)} cents`;
  dom.timingDevValue.textContent = `${timingDev.toFixed(2)}s`;

  // Classificação da pontuação
  if (score.total_score >= 85) {
    dom.scoreRating.textContent = "Excelente! Performance de alto nível";
    dom.scoreRating.style.color = "var(--accent-gold)";
  } else if (score.total_score >= 70) {
    dom.scoreRating.textContent = "Muito Bom! Ótima afinação e ritmo";
    dom.scoreRating.style.color = "var(--accent-green)";
  } else if (score.total_score >= 50) {
    dom.scoreRating.textContent = "Satisfatório! Dentro da média esperada";
    dom.scoreRating.style.color = "var(--accent-cyan)";
  } else {
    dom.scoreRating.textContent = "Abaixo da média. Pratique mais!";
    dom.scoreRating.style.color = "var(--accent-pink)";
  }

  renderPitchChart(score);
  dom.modalOverlay.classList.add("active");
}

function renderPitchChart(score) {
  const canvas = dom.pitchCanvas;
  const ctx = canvas.getContext("2d");
  const width = (canvas.width = canvas.offsetWidth * window.devicePixelRatio);
  const height = (canvas.height = canvas.offsetHeight * window.devicePixelRatio);

  ctx.clearRect(0, 0, width, height);

  // Fundo com grid sutil
  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  ctx.lineWidth = 1;
  for (let y = 0; y < height; y += 30) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  // Curva de Referência (Ciano)
  ctx.beginPath();
  ctx.strokeStyle = "#00f0ff";
  ctx.lineWidth = 3 * window.devicePixelRatio;
  ctx.shadowColor = "rgba(0, 240, 255, 0.5)";
  ctx.shadowBlur = 10;

  const points = 40;
  for (let i = 0; i <= points; i++) {
    const x = (i / points) * width;
    const y = height / 2 + Math.sin(i * 0.35) * (height * 0.28);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Curva do Usuário (Roxo / Rosa com pequenas variações baseadas na nota)
  ctx.beginPath();
  ctx.strokeStyle = "#ec4899";
  ctx.shadowColor = "rgba(236, 72, 153, 0.5)";
  ctx.lineWidth = 2.5 * window.devicePixelRatio;

  const errorFactor = (100 - score.total_score) / 100;
  for (let i = 0; i <= points; i++) {
    const x = (i / points) * width;
    const noise = (Math.sin(i * 1.5) + Math.cos(i * 0.8)) * (errorFactor * 25);
    const y = height / 2 + Math.sin(i * 0.35) * (height * 0.28) + noise;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

// ==========================================================================
// Utilitários
// ==========================================================================

function formatTime(totalSeconds) {
  if (isNaN(totalSeconds) || totalSeconds < 0) return "00:00";
  const mins = Math.floor(totalSeconds / 60);
  const secs = Math.floor(totalSeconds % 60);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
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

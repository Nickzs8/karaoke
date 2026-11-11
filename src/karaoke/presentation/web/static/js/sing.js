/**
 * Controlador da Página 2: Palco do Karaokê, Player e Gravação Integrada
 */

import { api } from "./api.js?v=2.0.0";
import { AudioPlayer } from "./audio-player.js?v=2.0.1";
import { VoiceRecorder } from "./recorder.js?v=2.0.0";

// Instâncias Globais
const player = new AudioPlayer();
const recorder = new VoiceRecorder();

let currentSong = null;
let currentLyrics = [];
let isEvaluating = false;
let currentOffset = 0.0;
let autoEstimatedOffset = 0.0;
let activeLineWordElements = [];

// Elementos do DOM
const dom = {
  // Navegação e Header
  btnBack: document.getElementById("btnBack"),

  // Palco
  stageContainer: document.getElementById("stageContainer"),
  currentSongTitle: document.getElementById("currentSongTitle"),
  currentSongArtist: document.getElementById("currentSongArtist"),
  lyricsBox: document.getElementById("lyricsBox"),

  // Barra de Sincronia
  syncBar: document.getElementById("syncBar"),
  syncValueDisplay: document.getElementById("syncValueDisplay"),
  btnSyncMinusLarge: document.getElementById("btnSyncMinusLarge"),
  btnSyncMinusSmall: document.getElementById("btnSyncMinusSmall"),
  btnSyncPlusSmall: document.getElementById("btnSyncPlusSmall"),
  btnSyncPlusLarge: document.getElementById("btnSyncPlusLarge"),
  btnSyncReset: document.getElementById("btnSyncReset"),
  btnSyncAuto: document.getElementById("btnSyncAuto"),

  // Controles do Player e Gravação
  currentTimeLabel: document.getElementById("currentTimeLabel"),
  totalTimeLabel: document.getElementById("totalTimeLabel"),
  progressBarContainer: document.getElementById("progressBarContainer"),
  progressBarFill: document.getElementById("progressBarFill"),

  // Botão Unificado Play & Record
  btnPlayRecord: document.getElementById("btnPlayRecord"),
  playIcon: document.getElementById("playIcon"),
  playRecordLabel: document.getElementById("playRecordLabel"),
  btnFinishSinging: document.getElementById("btnFinishSinging"),

  // Indicador de Carregamento
  stageLoadingBox: document.getElementById("stageLoadingBox"),
  stageLoadingText: document.getElementById("stageLoadingText"),
  stageLoadingStep: document.getElementById("stageLoadingStep"),

  // Modal de Pontuação
  modalOverlay: document.getElementById("modalOverlay"),
  scoreNumber: document.getElementById("scoreNumber"),
  scoreRating: document.getElementById("scoreRating"),
  pitchScoreValue: document.getElementById("pitchScoreValue"),
  timingScoreValue: document.getElementById("timingScoreValue"),
  coverageValue: document.getElementById("coverageValue"),
  latencyValue: document.getElementById("latencyValue"),
  centsErrorValue: document.getElementById("centsErrorValue"),
  timingDevValue: document.getElementById("timingDevValue"),
  btnRetryModal: document.getElementById("btnRetryModal"),
  btnBackToCatalogModal: document.getElementById("btnBackToCatalogModal"),
};

// Inicialização
document.addEventListener("DOMContentLoaded", async () => {
  setupSyncControls();
  setupPlayerCallbacks();
  setupUnifiedPlayRecord();
  setupModalEvents();

  await loadCurrentSongFromUrl();
});

// ==========================================================================
// 1. Carregamento da Música pela URL (?id=...)
// ==========================================================================

async function loadCurrentSongFromUrl() {
  const urlParams = new URLSearchParams(window.location.search);
  const songId = urlParams.get("id");

  if (!songId) {
    alert("Nenhuma música especificada. Redirecionando para o catálogo...");
    window.location.replace("/");
    return;
  }

  showStageLoading("Carregando música...", "Buscando áudio instrumental e letra...");

  try {
    // Carregamento defensivo com fallback para api.getSongs
    let song = null;
    if (typeof api.getSong === "function") {
      try {
        song = await api.getSong(songId);
      } catch {
        song = null;
      }
    }

    if (!song && typeof api.getSongs === "function") {
      const songs = await api.getSongs(false);
      song = songs.find((s) => s.id === songId);
    }

    if (!song) {
      throw new Error("Música não encontrada no catálogo.");
    }

    currentSong = song;

    dom.currentSongTitle.textContent = currentSong.title;
    dom.currentSongArtist.textContent = currentSong.artist;
    document.title = `Karaokê - ${currentSong.title} (${currentSong.artist})`;

    // Carrega letra sincronizada
    try {
      const lyricsData = await api.getLyrics(songId);
      currentLyrics = lyricsData.lines || [];
      autoEstimatedOffset =
        typeof lyricsData.estimated_offset === "number"
          ? lyricsData.estimated_offset
          : 0.0;
    } catch {
      currentLyrics = [];
      autoEstimatedOffset = 0.0;
    }

    // Verifica persistência de offset no localStorage por música
    const storageKey = `karaoke_offset_${songId}`;
    const savedOffset = localStorage.getItem(storageKey);

    if (savedOffset !== null) {
      currentOffset = parseFloat(savedOffset) || 0.0;
    } else if (Math.abs(autoEstimatedOffset) >= 0.2) {
      currentOffset = autoEstimatedOffset;
    } else {
      currentOffset = 0.0;
    }

    updateSyncDisplay(currentOffset, autoEstimatedOffset);
    renderLyrics(currentLyrics);

    // Inicializa o player com a faixa instrumental e offset
    if (currentSong.instrumental_url) {
      player.load(currentSong.instrumental_url, currentLyrics, currentOffset);
    } else {
      alert("Faixa instrumental não disponível para esta música.");
    }
  } catch (err) {
    alert(`Erro ao carregar música: ${err.message}`);
    window.location.replace("/");
  } finally {
    hideStageLoading();
  }
}

// ==========================================================================
// 2. Renderização de Letras Sincronizadas e Rastreamento de Palavras
// ==========================================================================

/**
 * Extrai e normaliza a lista de palavras/sílabas sincronizadas de um verso.
 * Aplica ancoragem temporal inteligente: se as palavras alinhadas divergirem do início do verso (especificação LRC),
 * calibra o início da frase para coincidir com line.start_time, preservando os ritmos e durações relativas de cada sílaba.
 * Elimina atrasos artificiais do aligner e fecha micro-lacunas para evitar interrupções bruscas do glow.
 * @param {Object} line
 * @returns {Array<{text: string, start_time: number, end_time: number}>}
 */
function getLineWords(line) {
  const lineStart = typeof line.start_time === "number" ? line.start_time : 0;
  const lineEnd = typeof line.end_time === "number" ? line.end_time : lineStart + 2;
  const lineDuration = Math.max(0.1, lineEnd - lineStart);

  if (line.words && Array.isArray(line.words) && line.words.length > 0) {
    const rawWords = line.words;
    const w0Start = typeof rawWords[0].start_time === "number" ? rawWords[0].start_time : lineStart;

    // Ancoragem temporal no início do verso (padrão LRC):
    // O timestamp do verso marca o início da primeira sílaba cantada.
    // Se o alinhamento da IA começou com atraso ou avanço, sincronizamos o início com lineStart.
    const anchorShift = w0Start - lineStart;

    const words = rawWords.map((w) => {
      const origStart = typeof w.start_time === "number" ? w.start_time : lineStart;
      const origEnd = typeof w.end_time === "number" ? w.end_time : origStart + 0.2;
      const adjustedStart = Number((origStart - anchorShift).toFixed(3));
      const adjustedEnd = Number((origEnd - anchorShift).toFixed(3));
      const validStart = Math.max(lineStart, adjustedStart);
      const validEnd = Math.max(validStart + 0.05, adjustedEnd);

      return {
        text: w.text,
        start_time: validStart,
        end_time: validEnd,
      };
    });

    // Fechamento de micro-lacunas (< 0.20s) entre palavras para evitar flickering do glow no meio de frases
    for (let j = 0; j < words.length - 1; j++) {
      const gap = words[j + 1].start_time - words[j].end_time;
      if (gap > 0 && gap <= 0.20) {
        words[j].end_time = words[j + 1].start_time;
      }
    }

    // Limitação de sustentação anômala na última palavra antes de pausas/solos instrumentais
    if (words.length > 0) {
      const lastIndex = words.length - 1;
      const lastWord = words[lastIndex];
      const lastDuration = lastWord.end_time - lastWord.start_time;

      let refDuration = 0.6;
      if (words.length > 1) {
        const sumPrev = words
          .slice(0, lastIndex)
          .reduce((acc, w) => acc + (w.end_time - w.start_time), 0);
        refDuration = sumPrev / lastIndex;
      }

      // Impede que a última palavra se estenda durante o solo/pausa posterior
      const maxAllowedDuration = Math.min(3.8, Math.max(3.0, refDuration * 3.5));
      if (lastDuration > maxAllowedDuration) {
        lastWord.end_time = Number((lastWord.start_time + maxAllowedDuration).toFixed(3));
      }
    }

    return words;
  }

  // Fallback para linhas sem palavras pré-alinhadas
  const rawWords = (line.text || "").trim().split(/\s+/).filter(Boolean);
  if (rawWords.length === 0) return [];

  // Se o verso for seguido por pausa instrumental longa, limita a duração para um ritmo vocal natural (~0.55s por palavra)
  const maxPhraseDuration = Math.max(1.5, rawWords.length * 0.55);
  const effectiveDuration = Math.min(lineDuration, maxPhraseDuration);
  const wordDur = effectiveDuration / rawWords.length;

  return rawWords.map((wordText, idx) => ({
    text: wordText,
    start_time: Number((lineStart + idx * wordDur).toFixed(3)),
    end_time: Number((lineStart + (idx + 1) * wordDur).toFixed(3)),
  }));
}

function renderLyrics(lines) {
  dom.lyricsBox.innerHTML = "";
  activeLineWordElements = [];

  if (!lines || lines.length === 0) {
    dom.lyricsBox.innerHTML = `
      <div style="padding: 60px 20px; color: var(--text-dim);">
        <p style="font-size: 1.15rem; margin-bottom: 8px; color: var(--text-main);">Letra sincronizada não disponível para esta faixa.</p>
        <p style="font-size: 0.85rem;">Siga o playback instrumental e cante à vontade!</p>
      </div>
    `;
    return;
  }

  lines.forEach((line, lineIndex) => {
    const div = document.createElement("div");
    div.className = "lyric-line";
    div.id = `line-${lineIndex}`;
    div.dataset.index = lineIndex;
    div.dataset.startTime = line.start_time;
    div.title = "Clique para saltar o playback para este verso";

    const words = getLineWords(line);
    line._computedWords = words;

    words.forEach((word, wordIndex) => {
      const span = document.createElement("span");
      span.className = "lyric-word word-future";
      span.id = `word-${lineIndex}-${wordIndex}`;
      span.dataset.start = word.start_time;
      span.dataset.end = word.end_time;
      span.textContent = word.text;
      div.appendChild(span);

      if (wordIndex < words.length - 1) {
        div.appendChild(document.createTextNode(" "));
      }
    });

    div.addEventListener("click", () => {
      const targetTime = Math.max(0, line.start_time + player.getLyricsOffset());
      player.seek(targetTime);
    });

    dom.lyricsBox.appendChild(div);
  });
}

/**
 * Atualiza o preenchimento visual contínuo da palavra/sílaba na linha ativa.
 * Calcula (effectiveTime - start) / (end - start) e aplica gradiente no tempo exato da sustentação vocal.
 * @param {number} effectiveTime Tempo de reprodução ajustado pelo offset
 */
function updateActiveWords(effectiveTime) {
  if (activeLineWordElements.length === 0) return;

  for (let k = 0; k < activeLineWordElements.length; k++) {
    const item = activeLineWordElements[k];
    const el = item.el;
    if (!el) continue;

    const start = item.word.start_time;
    const end = item.word.end_time;

    if (effectiveTime < start) {
      if (!el.classList.contains("word-future")) {
        el.className = "lyric-word word-future";
        el.style.removeProperty("--word-progress");
      }
    } else if (effectiveTime >= end) {
      if (!el.classList.contains("word-past")) {
        el.className = "lyric-word word-past";
        el.style.setProperty("--word-progress", "100%");
      }
    } else {
      // Sílaba cantada no exato momento!
      const duration = Math.max(0.04, end - start);
      const progress = Math.min(100, Math.max(0, ((effectiveTime - start) / duration) * 100));
      if (!el.classList.contains("word-active")) {
        el.className = "lyric-word word-active";
      }
      el.style.setProperty("--word-progress", `${progress.toFixed(1)}%`);
    }
  }
}

// ==========================================================================
// 3. Barra de Controle de Sincronia DAW
// ==========================================================================

function setupSyncControls() {
  function applyOffset(newOffset) {
    currentOffset = Math.round(newOffset * 10) / 10;
    if (currentSong) {
      localStorage.setItem(`karaoke_offset_${currentSong.id}`, currentOffset.toString());
    }
    player.setLyricsOffset(currentOffset);
    updateSyncDisplay(currentOffset, autoEstimatedOffset);
  }

  dom.btnSyncMinusLarge.addEventListener("click", () => applyOffset(currentOffset - 1.0));
  dom.btnSyncMinusSmall.addEventListener("click", () => applyOffset(currentOffset - 0.2));
  dom.btnSyncPlusSmall.addEventListener("click", () => applyOffset(currentOffset + 0.2));
  dom.btnSyncPlusLarge.addEventListener("click", () => applyOffset(currentOffset + 1.0));
  dom.btnSyncReset.addEventListener("click", () => applyOffset(0.0));
  dom.btnSyncAuto.addEventListener("click", () => applyOffset(autoEstimatedOffset));

  window.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
    if (e.key === "[") {
      applyOffset(currentOffset - (e.shiftKey ? 1.0 : 0.2));
    } else if (e.key === "]") {
      applyOffset(currentOffset + (e.shiftKey ? 1.0 : 0.2));
    }
  });
}

function updateSyncDisplay(offset, autoOffset) {
  const sign = offset > 0 ? "+" : "";
  dom.syncValueDisplay.textContent = `${sign}${offset.toFixed(1)}s`;

  if (autoOffset && Math.abs(autoOffset) >= 0.2) {
    dom.btnSyncAuto.style.display = "inline-block";
    const autoSign = autoOffset > 0 ? "+" : "";
    dom.btnSyncAuto.textContent = `Auto (${autoSign}${autoOffset.toFixed(1)}s)`;
  } else {
    dom.btnSyncAuto.style.display = "none";
  }
}

// ==========================================================================
// 4. Botão Unificado: Play & Gravação Simultânea
// ==========================================================================

function setupUnifiedPlayRecord() {
  dom.btnPlayRecord.addEventListener("click", async () => {
    try {
      if (player.isPlaying()) {
        // Pausa áudio e gravação
        player.pause();
        recorder.pause();
        setControlState(false, true);
      } else {
        // Começa a tocar e gravar
        if (!recorder.isRecording) {
          await recorder.start();
        } else {
          recorder.resume();
        }
        await player.play();
        setControlState(true);
      }
    } catch (err) {
      alert(`Permissão de microfone necessária para cantar: ${err.message}`);
    }
  });

  // Botão Finalizar e Avaliar
  dom.btnFinishSinging.addEventListener("click", async () => {
    await finishPerformanceAndScore();
  });
}

function setControlState(isPlaying, isPaused = false) {
  if (isPlaying) {
    dom.btnPlayRecord.classList.add("recording");
    dom.playIcon.textContent = "❚❚";
    dom.playRecordLabel.textContent = "Pausar";
  } else {
    dom.btnPlayRecord.classList.remove("recording");
    dom.playIcon.textContent = "▶";
    dom.playRecordLabel.textContent = isPaused ? "Continuar" : "Começar a Cantar";
  }
}

// ==========================================================================
// 5. Callbacks do Player de Áudio
// ==========================================================================

function setupPlayerCallbacks() {
  player.onTimeUpdate = (currentTime, duration, percent) => {
    dom.currentTimeLabel.textContent = formatTime(currentTime);
    dom.totalTimeLabel.textContent = formatTime(duration);
    dom.progressBarFill.style.width = `${percent}%`;
  };

  player.onLineChange = (line, index) => {
    document.querySelectorAll(".lyric-line").forEach((el, i) => {
      el.classList.remove("active");
      if (index >= 0 && i < index) {
        el.classList.add("past");
        el.querySelectorAll(".lyric-word").forEach((w) => {
          w.className = "lyric-word word-past";
          w.style.setProperty("--word-progress", "100%");
        });
      } else if (index >= 0 && i > index) {
        el.classList.remove("past");
        el.querySelectorAll(".lyric-word").forEach((w) => {
          w.className = "lyric-word word-future";
          w.style.removeProperty("--word-progress");
        });
      } else {
        el.classList.remove("past");
      }
    });

    if (index >= 0 && currentLyrics[index]) {
      const activeEl = document.getElementById(`line-${index}`);
      if (activeEl) {
        activeEl.classList.add("active");
        activeEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }

      const words = currentLyrics[index]._computedWords || [];
      activeLineWordElements = words.map((w, wIdx) => ({
        word: w,
        el: document.getElementById(`word-${index}-${wIdx}`),
      }));

      const effectiveTime = player.getCurrentTime() - player.getLyricsOffset();
      updateActiveWords(effectiveTime);
    } else {
      activeLineWordElements = [];
      dom.lyricsBox.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  player.onHighResTimeUpdate = (currentTime, effectiveTime) => {
    updateActiveWords(effectiveTime);
  };

  player.onPlay = () => setControlState(true);
  player.onPause = () => setControlState(false, true);

  player.onEnded = async () => {
    setControlState(false);
    if (recorder.isRecording) {
      await finishPerformanceAndScore();
    }
  };

  // Clique na timeline para seek
  dom.progressBarContainer.addEventListener("click", (e) => {
    const rect = dom.progressBarContainer.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percent = (clickX / rect.width) * 100;
    player.seekPercent(percent);
  });
}

// ==========================================================================
// 6. Finalização da Performance e Avaliação
// ==========================================================================

async function finishPerformanceAndScore() {
  if (isEvaluating) return;
  isEvaluating = true;

  player.pause();
  setControlState(false);

  showStageLoading("Avaliando performance vocal...", "Comparando afinação melódica e ritmo...");

  try {
    const audioBlob = await recorder.stop();

    if (!audioBlob || audioBlob.size === 0) {
      alert("Nenhum áudio foi gravado. Cante enquanto o playback toca!");
      return;
    }

    const scoreResult = await api.evaluatePerformance(currentSong.id, audioBlob);
    showScoreModal(scoreResult);
  } catch (err) {
    alert(`Erro na avaliação da performance: ${err.message}`);
  } finally {
    hideStageLoading();
    isEvaluating = false;
  }
}

// ==========================================================================
// 7. Modal de Avaliação e Gráfico Melódico
// ==========================================================================

function setupModalEvents() {
  dom.btnRetryModal.addEventListener("click", async () => {
    dom.modalOverlay.classList.remove("active");
    player.seek(0);
    try {
      await recorder.start();
      await player.play();
      setControlState(true);
    } catch (err) {
      console.error("Falha ao reiniciar performance:", err);
    }
  });
}

function showScoreModal(score) {
  dom.scoreNumber.textContent = Math.round(score.total_score);
  dom.pitchScoreValue.textContent = `${score.pitch_score.toFixed(1)}%`;
  dom.timingScoreValue.textContent = `${score.timing_score.toFixed(1)}%`;

  const coverage = score.details?.coverage_ratio ?? 100;
  if (dom.coverageValue) {
    dom.coverageValue.textContent = `${coverage.toFixed(1)}%`;
  }

  const latency = score.details?.global_latency_seconds ?? 0;
  if (dom.latencyValue) {
    const latSign = latency > 0 ? "+" : "";
    dom.latencyValue.textContent = `${latSign}${(latency * 1000).toFixed(0)} ms`;
  }

  const meanCents =
    score.details?.mean_pitch_error_cents ??
    score.details?.mean_cents_error ??
    0;
  const timingDev = score.details?.mean_timing_deviation_seconds ?? 0;

  dom.centsErrorValue.textContent = `${meanCents.toFixed(1)} cents`;
  dom.timingDevValue.textContent = `${timingDev.toFixed(2)}s`;

  // Classificação da pontuação com paleta Toggl Track
  if (score.total_score >= 85) {
    dom.scoreRating.textContent = "Excelente! Performance de alto nível";
    dom.scoreRating.style.color = "var(--color-magenta)";
  } else if (score.total_score >= 70) {
    dom.scoreRating.textContent = "Muito Bom! Ótima afinação e ritmo";
    dom.scoreRating.style.color = "var(--color-amber)";
  } else if (score.total_score >= 50) {
    dom.scoreRating.textContent = "Satisfatório! Dentro da média esperada";
    dom.scoreRating.style.color = "var(--color-heather)";
  } else {
    dom.scoreRating.textContent = "Abaixo da média. Pratique mais!";
    dom.scoreRating.style.color = "#dc2626";
  }

  dom.modalOverlay.classList.add("active");
}

// ==========================================================================
// Utilitários
// ==========================================================================

function showStageLoading(title, step) {
  dom.stageLoadingText.textContent = title;
  dom.stageLoadingStep.textContent = step;
  dom.stageLoadingBox.style.display = "block";
}

function hideStageLoading() {
  dom.stageLoadingBox.style.display = "none";
}

function formatTime(totalSeconds) {
  if (isNaN(totalSeconds) || totalSeconds < 0) return "00:00";
  const mins = Math.floor(totalSeconds / 60);
  const secs = Math.floor(totalSeconds % 60);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

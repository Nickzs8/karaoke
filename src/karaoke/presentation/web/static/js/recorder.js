/**
 * Módulo de Gravação de Áudio via MediaRecorder API e VU Meter
 */

export class VoiceRecorder {
  constructor() {
    this.stream = null;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;

    // Medidor de volume de entrada (VU Meter)
    this.audioContext = null;
    this.analyser = null;
    this.animFrameId = null;

    // Callbacks
    this.onVolumeChange = null;
    this.onRecordingStart = null;
    this.onRecordingStop = null;
  }

  /**
   * Solicita acesso ao microfone do usuário se ainda não permitido.
   */
  async requestPermission() {
    if (!this.stream) {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      this._setupAudioMeter(this.stream);
    }
    return this.stream;
  }

  _setupAudioMeter(stream) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioCtx();
      const source = this.audioContext.createMediaStreamSource(stream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      source.connect(this.analyser);

      const dataArray = new Uint8Array(this.analyser.frequencyBinCount);

      const checkVolume = () => {
        if (this.isRecording && this.analyser) {
          this.analyser.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const avg = sum / dataArray.length;
          const normalized = Math.min(100, Math.round((avg / 128) * 100));

          if (this.onVolumeChange) {
            this.onVolumeChange(normalized);
          }
        }
        this.animFrameId = requestAnimationFrame(checkVolume);
      };

      checkVolume();
    } catch (e) {
      console.warn("Análise de volume de áudio não suportada:", e);
    }
  }

  /**
   * Inicia a captura de áudio da performance.
   */
  async start() {
    await this.requestPermission();

    this.audioChunks = [];

    // Escolhe o melhor MIME type suportado pelo navegador
    let mimeType = "audio/webm";
    if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
      mimeType = "audio/webm;codecs=opus";
    } else if (MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")) {
      mimeType = "audio/ogg;codecs=opus";
    }

    this.mediaRecorder = new MediaRecorder(this.stream, { mimeType });

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        this.audioChunks.push(event.data);
      }
    };

    this.mediaRecorder.start(250); // Coleta dados a cada 250ms
    this.isRecording = true;

    if (this.audioContext && this.audioContext.state === "suspended") {
      this.audioContext.resume();
    }

    if (this.onRecordingStart) this.onRecordingStart();
  }

  /**
   * Finaliza a gravação e retorna o Blob consolidado de áudio gravado.
   * @returns {Promise<Blob>}
   */
  stop() {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder || !this.isRecording) {
        resolve(new Blob(this.audioChunks, { type: "audio/webm" }));
        return;
      }

      this.mediaRecorder.onstop = () => {
        this.isRecording = false;
        const blob = new Blob(this.audioChunks, {
          type: this.mediaRecorder.mimeType || "audio/webm",
        });

        if (this.onRecordingStop) this.onRecordingStop(blob);
        resolve(blob);
      };

      this.mediaRecorder.onerror = (event) => {
        this.isRecording = false;
        reject(event.error);
      };

      this.mediaRecorder.stop();
    });
  }

  dispose() {
    if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
    if (this.audioContext) this.audioContext.close();
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
  }
}

(() => {
  const dialog = document.querySelector("#camera-dialog");
  if (!dialog) return;

  const video = document.querySelector("#camera-video");
  const stage = document.querySelector("#camera-stage");
  const guide = document.querySelector("#ine-guide");
  const canvas = document.querySelector("#camera-canvas");
  const title = document.querySelector("#camera-title");
  const message = document.querySelector("#camera-message");
  const capture = document.querySelector("#camera-capture");
  const cancel = document.querySelector("#camera-cancel");
  const lightBadge = document.querySelector("#quality-light");
  const focusBadge = document.querySelector("#quality-focus");
  const glareBadge = document.querySelector("#quality-glare");
  let stream = null;
  let target = null;
  let qualityTimer = null;

  function stopCamera() {
    if (qualityTimer) window.clearInterval(qualityTimer);
    qualityTimer = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
  }

  function closeCamera() {
    stopCamera();
    if (dialog.open) dialog.close();
  }

  async function openCamera(fieldName) {
    target = document.querySelector(`#${fieldName}`);
    title.textContent = fieldName === "front" ? "Fotografiar frente" : "Fotografiar reverso";
    message.textContent = fieldName === "front"
      ? "Frente: centre toda la credencial. Deben verse con nitidez CURP, clave, sección y vigencia."
      : "Reverso: centre toda la credencial y enfoque especialmente las tres líneas de la parte inferior.";
    if (!navigator.mediaDevices?.getUserMedia) {
      target.click();
      return;
    }
    dialog.showModal();
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
      video.srcObject = stream;
      await video.play();
      const track = stream.getVideoTracks()[0];
      const capabilities = track.getCapabilities?.() || {};
      const cameraSettings = {};
      if (capabilities.focusMode?.includes("continuous")) cameraSettings.focusMode = "continuous";
      if (capabilities.exposureMode?.includes("continuous")) cameraSettings.exposureMode = "continuous";
      if (capabilities.whiteBalanceMode?.includes("continuous")) cameraSettings.whiteBalanceMode = "continuous";
      if (Object.keys(cameraSettings).length) {
        track.applyConstraints({ advanced: [cameraSettings] }).catch(() => {});
      }
      updateLiveQuality();
      qualityTimer = window.setInterval(updateLiveQuality, 650);
    } catch (_error) {
      closeCamera();
      target.click();
    }
  }

  function showPreview(fieldName, file) {
    const preview = document.querySelector(`#${fieldName}-preview`);
    const status = document.querySelector(`#${fieldName}-status`);
    preview.src = URL.createObjectURL(file);
    preview.classList.add("ready");
    status.textContent = "Fotografía lista";
  }

  function cropGeometry(padding = 0) {
    const stageBox = stage.getBoundingClientRect();
    const guideBox = guide.getBoundingClientRect();
    const scale = Math.max(stageBox.width / video.videoWidth, stageBox.height / video.videoHeight);
    const hiddenX = (video.videoWidth * scale - stageBox.width) / 2;
    const hiddenY = (video.videoHeight * scale - stageBox.height) / 2;
    let x = (guideBox.left - stageBox.left + hiddenX) / scale;
    let y = (guideBox.top - stageBox.top + hiddenY) / scale;
    let width = guideBox.width / scale;
    let height = guideBox.height / scale;
    x -= width * padding;
    y -= height * padding;
    width *= 1 + padding * 2;
    height *= 1 + padding * 2;
    x = Math.max(0, x);
    y = Math.max(0, y);
    width = Math.min(video.videoWidth - x, width);
    height = Math.min(video.videoHeight - y, height);
    return { x, y, width, height };
  }

  function drawCurrentFrame(output, width, padding = 0) {
    const crop = cropGeometry(padding);
    output.width = width;
    output.height = Math.round(width / 1.586);
    output.getContext("2d").drawImage(
      video, crop.x, crop.y, crop.width, crop.height,
      0, 0, output.width, output.height,
    );
  }

  function photoQuality(sourceCanvas) {
    const sample = document.createElement("canvas");
    sample.width = 320;
    sample.height = Math.round(320 / 1.586);
    const context = sample.getContext("2d", { willReadFrequently: true });
    context.drawImage(sourceCanvas, 0, 0, sample.width, sample.height);
    const pixels = context.getImageData(0, 0, sample.width, sample.height).data;
    let brightness = 0;
    let edges = 0;
    let comparisons = 0;
    let highlights = 0;
    let shadows = 0;
    const gray = (offset) => pixels[offset] * .299 + pixels[offset + 1] * .587 + pixels[offset + 2] * .114;
    for (let y = 1; y < sample.height; y += 2) {
      for (let x = 1; x < sample.width; x += 2) {
        const offset = (y * sample.width + x) * 4;
        const value = gray(offset);
        brightness += value;
        if (value > 248) highlights += 1;
        if (value < 28) shadows += 1;
        edges += Math.abs(value - gray(offset - 4));
        edges += Math.abs(value - gray(offset - sample.width * 4));
        comparisons += 2;
      }
    }
    const samples = comparisons / 2;
    return {
      brightness: brightness / samples,
      sharpness: edges / comparisons,
      glare: highlights / samples,
      darkness: shadows / samples,
    };
  }

  function setBadge(element, label, state) {
    element.textContent = label;
    element.className = state;
  }

  function renderQuality(quality) {
    const lightState = quality.brightness < 48 || quality.brightness > 238 || quality.darkness > .28 ? "bad"
      : (quality.brightness < 65 || quality.brightness > 222 ? "warn" : "good");
    const focusState = quality.sharpness < 3.8 ? "bad" : (quality.sharpness < 5.5 ? "warn" : "good");
    const glareState = quality.glare > .15 ? "bad" : (quality.glare > .07 ? "warn" : "good");
    setBadge(lightBadge, lightState === "good" ? "Luz bien" : "Revise luz", lightState);
    setBadge(focusBadge, focusState === "good" ? "Enfoque bien" : "Espere enfoque", focusState);
    setBadge(glareBadge, glareState === "good" ? "Sin reflejo" : "Incline la INE", glareState);
  }

  function updateLiveQuality() {
    if (!stream || !video.videoWidth) return;
    const sample = document.createElement("canvas");
    drawCurrentFrame(sample, 320);
    renderQuality(photoQuality(sample));
  }

  function frameScore(quality) {
    return quality.sharpness * 3
      - Math.abs(quality.brightness - 145) * .025
      - quality.glare * 90
      - quality.darkness * 50;
  }

  document.querySelectorAll(".camera-open").forEach((button) => {
    button.addEventListener("click", () => openCamera(button.dataset.target));
  });

  document.querySelectorAll('input[type="file"]').forEach((input) => {
    input.addEventListener("change", () => {
      if (input.files?.[0]) showPreview(input.id, input.files[0]);
    });
  });

  capture.addEventListener("click", async () => {
    if (!target || !video.videoWidth) return;
    capture.disabled = true;
    message.textContent = "No se mueva: seleccionando el cuadro más nítido…";
    const frames = [];
    for (let index = 0; index < 3; index += 1) {
      const frame = document.createElement("canvas");
      drawCurrentFrame(frame, Math.max(1400, Math.min(2200, video.videoWidth)), .055);
      const quality = photoQuality(frame);
      frames.push({ frame, quality, score: frameScore(quality) });
      if (index < 2) await new Promise((resolve) => window.setTimeout(resolve, 170));
    }
    const best = frames.sort((a, b) => b.score - a.score)[0];
    const quality = best.quality;
    renderQuality(quality);
    capture.disabled = false;
    if (quality.brightness < 42 || quality.darkness > .38) {
      message.textContent = "La foto está muy oscura. Mueva la INE hacia una luz uniforme y vuelva a tomarla.";
      return;
    }
    if (quality.brightness > 242 || quality.glare > .17) {
      message.textContent = "Hay demasiado reflejo. Incline ligeramente la INE y vuelva a tomarla.";
      return;
    }
    if (quality.sharpness < 3.8) {
      message.textContent = "La foto está borrosa. Acerque la INE, espere a que enfoque y vuelva a tomarla.";
      return;
    }
    canvas.width = best.frame.width;
    canvas.height = best.frame.height;
    canvas.getContext("2d").drawImage(best.frame, 0, 0);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], `${target.id}-ine.jpg`, { type: "image/jpeg" });
      const transfer = new DataTransfer();
      transfer.items.add(file);
      target.files = transfer.files;
      showPreview(target.id, file);
      closeCamera();
    }, "image/jpeg", 0.95);
  });

  cancel.addEventListener("click", closeCamera);
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); closeCamera(); });
})();

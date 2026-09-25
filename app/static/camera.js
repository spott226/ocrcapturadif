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
  let stream = null;
  let target = null;

  function stopCamera() {
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

  document.querySelectorAll(".camera-open").forEach((button) => {
    button.addEventListener("click", () => openCamera(button.dataset.target));
  });

  document.querySelectorAll('input[type="file"]').forEach((input) => {
    input.addEventListener("change", () => {
      if (input.files?.[0]) showPreview(input.id, input.files[0]);
    });
  });

  capture.addEventListener("click", () => {
    if (!target || !video.videoWidth) return;
    const stageBox = stage.getBoundingClientRect();
    const guideBox = guide.getBoundingClientRect();
    const scale = Math.max(stageBox.width / video.videoWidth, stageBox.height / video.videoHeight);
    const renderedWidth = video.videoWidth * scale;
    const renderedHeight = video.videoHeight * scale;
    const hiddenX = (renderedWidth - stageBox.width) / 2;
    const hiddenY = (renderedHeight - stageBox.height) / 2;
    const sourceX = Math.max(0, (guideBox.left - stageBox.left + hiddenX) / scale);
    const sourceY = Math.max(0, (guideBox.top - stageBox.top + hiddenY) / scale);
    const sourceWidth = Math.min(video.videoWidth - sourceX, guideBox.width / scale);
    const sourceHeight = Math.min(video.videoHeight - sourceY, guideBox.height / scale);
    canvas.width = Math.max(1200, Math.round(sourceWidth));
    canvas.height = Math.round(canvas.width / 1.586);
    canvas.getContext("2d").drawImage(
      video, sourceX, sourceY, sourceWidth, sourceHeight,
      0, 0, canvas.width, canvas.height,
    );
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

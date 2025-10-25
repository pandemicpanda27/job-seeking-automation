function initializeResumeUpload() {
  const fileInput = document.getElementById("resumeFile");
  const uploadTrigger = document.getElementById("uploadTrigger");
  const messageBox = document.getElementById("resumeMessage");
  const resultContainer = document.getElementById("parsedContainer");

  if (!fileInput || !uploadTrigger || !resultContainer) return;

  // Remove previous listeners by replacing elements
  const newFileInput = fileInput.cloneNode(true);
  const newUploadTrigger = uploadTrigger.cloneNode(true);

  fileInput.parentNode.replaceChild(newFileInput, fileInput);
  uploadTrigger.parentNode.replaceChild(newUploadTrigger, uploadTrigger);

  newUploadTrigger.addEventListener("click", () => {
    newFileInput.click();
  });

  newFileInput.addEventListener("change", async () => {
    const file = newFileInput.files[0];
    if (!file) return;

    if (file.type !== "application/pdf") {
      alert("Only PDF files are allowed.");
      newFileInput.value = "";
      messageBox.style.display = "none";
      return;
    }

    messageBox.style.display = "block";

    const formData = new FormData();
    formData.append("resume", file);

    resultContainer.innerHTML = `
      <p>Email: <span id="parsed-email" contenteditable="true">Parsing...</span></p>
      <p>Phone: <span id="parsed-phone" contenteditable="true">Parsing...</span></p>
      <p>Skills: <span id="parsed-skills" contenteditable="true">Parsing...</span></p>
      <button id="save-edits" class="btn btn-success mt-2">Save Changes</button>
      <small class="text-muted">(You can click and edit these fields)</small>
    `;

    try {
      const response = await fetch("/api/parse-resume", {
        method: "POST",
        body: formData
      });

      const parsedData = await response.json();

      if (!response.ok) {
        throw new Error(parsedData.message || parsedData.error || "Failed to parse resume.");
      }

      const { email, phone, skills } = parsedData.data || {};

      document.getElementById("parsed-email").textContent = email || "Not found";
      document.getElementById("parsed-phone").textContent = phone || "Not found";
      document.getElementById("parsed-skills").textContent =
        skills && skills.length > 0 ? skills.join(", ") : "None found";
    } catch (error) {
      console.error("Error parsing resume:", error);
      document.getElementById("parsed-email").textContent = "Error";
      document.getElementById("parsed-phone").textContent = "Error";
      document.getElementById("parsed-skills").textContent = "Error";
    }

    attachSaveListener();
  });
}

function attachSaveListener() {
  const oldButton = document.getElementById("save-edits");
  if (!oldButton) return;

  const newButton = oldButton.cloneNode(true);
  oldButton.parentNode.replaceChild(newButton, oldButton);

  newButton.addEventListener("click", async () => {
    const updatedEmail = document.getElementById("parsed-email").textContent.trim();
    const updatedPhone = document.getElementById("parsed-phone").textContent.trim();
    const updatedSkills = document.getElementById("parsed-skills").textContent
      .split(",")
      .map(skill => skill.trim())
      .filter(Boolean);

    const payload = {
      email: updatedEmail,
      phone: updatedPhone,
      skills: updatedSkills
    };

    try {
      const response = await fetch("/api/parse-resume/save-edits", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json();
      if (response.ok) {
        alert("Changes saved successfully!");
        window.location.href = "/filtered-jobs";
      } else {
        alert("Failed to save changes: " + (result.message || result.error || "Unknown error"));
      }
    } catch (error) {
      console.error("Error saving edits:", error);
      alert("An error occurred while saving changes.");
    }
  });
}

// Run on initial page load
document.addEventListener("DOMContentLoaded", () => {
  initializeResumeUpload();
  window.reinitializeResumeUpload = initializeResumeUpload;
});

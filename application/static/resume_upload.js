document.addEventListener("DOMContentLoaded", function () {
  const resumeInput = document.getElementById("resumeFile");
  const messageBox = document.getElementById("resumeMessage");

  resumeInput.addEventListener("change", function () {
    const file = resumeInput.files[0];
    if (file && file.type === "application/pdf") {
      messageBox.style.display = "block";
    } else {
      messageBox.style.display = "none";
    }
  });
});

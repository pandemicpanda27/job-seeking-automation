document.addEventListener('DOMContentLoaded', function () {
  const searchButton = document.getElementById('customSearchBtn');
  const loadingIndicator = document.getElementById('loadingIndicator');
  const resultsContainer = document.getElementById('resultsContainer');
  const welcomeMessage = document.getElementById('welcomeMessage');

  console.log('search.js loaded. searchButton:', searchButton);

  if (!searchButton) {
    console.error('Button #customSearchBtn not found in DOM!');
    return;
  }

  function showLoading() {
    console.log('Showing loading indicator');
    if (welcomeMessage) welcomeMessage.style.display = 'none';
    loadingIndicator.classList.remove('d-none');
    resultsContainer.innerHTML = '';
  }

  function hideLoading() {
    console.log('Hiding loading indicator');
    loadingIndicator.classList.add('d-none');
  }

  function showAlert(message, type) {
    console.log('Showing alert:', message, type);
    resultsContainer.innerHTML = `
      <div class="alert alert-${type}">
        ${message}
      </div>
    `;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function displayJobs(jobs) {
    console.log('displayJobs called with jobs:', jobs);
    if (!jobs.length) {
      showAlert('No jobs found for your criteria.', 'info');
      return;
    }

    let html = jobs.map(job => `
      <div class="job-card mb-3 p-3 border rounded">
        <h5>${escapeHtml(job.title || 'Untitled')}</h5>
        <p><strong>Company:</strong> ${escapeHtml(job.company || 'Unknown')}</p>
        <p><strong>Location:</strong> ${escapeHtml(job.location || 'Unknown')}</p>
        <p>${escapeHtml(job.description || 'No description available.')}</p>
        ${job.url ? `<a href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer">View Job</a>` : ''}
      </div>
    `).join('');

    resultsContainer.innerHTML = html;
  }

  searchButton.addEventListener('click', async function () {
    console.log('Search button clicked');

    const jobTitleInput = document.getElementById('jobTitle');
    const locationInput = document.getElementById('location');

    const jobTitle = jobTitleInput ? jobTitleInput.value.trim() : '';
    const location = locationInput ? locationInput.value.trim() : '';

    console.log('Inputs: jobTitle=', jobTitle, 'location=', location);

    if (!jobTitle) {
      showAlert('Please enter a job title.', 'warning');
      return;
    }

    showLoading();

    try {
      const queryParams = new URLSearchParams({ query: jobTitle, location });
      const response = await fetch(`/api/job-search?${queryParams.toString()}`);
      const data = await response.json();

      console.log('Response JSON:', data);

      if (!response.ok) {
        showAlert(data.message || 'An error occurred. Please try again.', 'danger');
        return;
      }

      if (data.success && Array.isArray(data.jobs)) {
        displayJobs(data.jobs);

        const uploadSection = document.getElementById("uploadSection");
        if (uploadSection) {
          uploadSection.style.display = "block";
        }

        if (window.reinitializeResumeUpload) {
          window.reinitializeResumeUpload();
        }
      } else {
        showAlert(data.message || 'No jobs found.', 'info');
      }
    } catch (error) {
      console.error('Fetch error:', error);
      showAlert('Something went wrong. Please try again.', 'danger');
    } finally {
      hideLoading();
    }
  });
});

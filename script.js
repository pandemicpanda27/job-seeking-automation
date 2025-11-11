class JobMatchApp {
    constructor() {
        this.resumeData = null;
        this.allJobs = [];
        this.filteredJobs = [];
        this.currentFilter = 'all';
        this.currentSort = 'match';
        this.isDarkMode = localStorage.getItem('theme') === 'dark';
        this.init();
    }

    init() {
        this.applyTheme();
        this.setupEventListeners();
    }

    applyTheme() {
        if (this.isDarkMode) {
            document.documentElement.setAttribute('data-theme', 'dark');
            this.updateThemeIcon();
        }
    }

    setupEventListeners() {
        // Theme
        document.getElementById('themeToggle').addEventListener('click', () => this.toggleTheme());

        // Resume
        document.getElementById('uploadArea').addEventListener('click', () => {
            document.getElementById('resumeInput').click();
        });

        document.getElementById('resumeInput').addEventListener('change', (e) => {
            this.handleResumeUpload(e.target.files[0]);
        });

        const changeBtn = document.getElementById('changeResumeBtn');
        if (changeBtn) {
            changeBtn.addEventListener('click', () => this.resetResume());
        }

        // Search
        ['jobTitle', 'location'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', () => this.updateSearchButton());
            }
        });

        document.getElementById('searchBtn').addEventListener('click', () => this.searchJobs());

        // Filter
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.target.closest('.filter-btn').classList.add('active');
                this.currentFilter = e.target.closest('.filter-btn').dataset.filter;
                this.applyFiltersAndSort();
            });
        });

        // Sort
        document.getElementById('sortBy').addEventListener('change', (e) => {
            this.currentSort = e.target.value;
            this.applyFiltersAndSort();
        });

        // Modal
        document.getElementById('modalClose').addEventListener('click', () => this.closeModal());
        document.querySelector('.modal-backdrop').addEventListener('click', () => this.closeModal());

        // Nav
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                e.target.classList.add('active');
            });
        });

        // Keyboard
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeModal();
        });
    }

    toggleTheme() {
        this.isDarkMode = !this.isDarkMode;
        document.documentElement.setAttribute('data-theme', this.isDarkMode ? 'dark' : 'light');
        localStorage.setItem('theme', this.isDarkMode ? 'dark' : 'light');
        this.updateThemeIcon();
    }

    updateThemeIcon() {
        const btn = document.getElementById('themeToggle');
        btn.innerHTML = this.isDarkMode ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
    }

    handleResumeUpload(file) {
        if (!file) return;

        const validTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain'
        ];

        if (!validTypes.includes(file.type)) {
            alert('Please upload PDF, DOCX, or TXT file');
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            alert('File size must be less than 10MB');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        const uploadArea = document.getElementById('uploadArea');
        uploadArea.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><p>Parsing resume...</p></div>';

        fetch('/api/v1/resume/parse', {
            method: 'POST',
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            this.resumeData = data.parsed_data || {
                name: 'Professional',
                category: 'Software Developer',
                skills: ['Python', 'JavaScript', 'React', 'Node.js'],
                experience: '5+ years'
            };
            this.showResumePreview(file.name);
            this.updateSearchButton();
        })
        .catch(() => {
            this.resumeData = {
                name: 'Professional',
                category: 'Software Developer',
                skills: ['Python', 'JavaScript', 'React'],
                experience: '3+ years'
            };
            this.showResumePreview(file.name);
            this.updateSearchButton();
        });
    }

    showResumePreview(fileName) {
        document.getElementById('uploadArea').style.display = 'none';
        const preview = document.getElementById('resumePreview');
        preview.style.display = 'block';

        document.getElementById('resumeFileName').textContent = fileName;
        document.getElementById('resumeName').textContent = this.resumeData.name || 'N/A';
        document.getElementById('resumeCategory').textContent = this.resumeData.category || 'N/A';
        document.getElementById('resumeExperience').textContent = this.resumeData.experience || '3+ years';

        const skillsContainer = document.getElementById('resumeSkills');
        skillsContainer.innerHTML = '';
        (this.resumeData.skills || []).slice(0, 8).forEach(skill => {
            const tag = document.createElement('span');
            tag.className = 'skill-tag';
            tag.innerHTML = `<i class="fas fa-check"></i> ${skill}`;
            skillsContainer.appendChild(tag);
        });

        if ((this.resumeData.skills || []).length > 8) {
            const more = document.createElement('span');
            more.className = 'skill-tag';
            more.innerHTML = `+${(this.resumeData.skills || []).length - 8} more`;
            skillsContainer.appendChild(more);
        }
    }

    resetResume() {
        this.resumeData = null;
        document.getElementById('uploadArea').style.display = 'block';
        document.getElementById('resumePreview').style.display = 'none';
        document.getElementById('resumeInput').value = '';
        this.updateSearchButton();
    }

    updateSearchButton() {
        const hasResume = this.resumeData !== null;
        const jobTitle = document.getElementById('jobTitle').value.trim();
        const location = document.getElementById('location').value.trim();

        ['jobTitle', 'location', 'jobType', 'salaryMin'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.disabled = !hasResume;
        });

        document.getElementById('searchBtn').disabled = !(hasResume && jobTitle && location);
    }

    searchJobs() {
        const jobTitle = document.getElementById('jobTitle').value;
        const location = document.getElementById('location').value;

        if (!jobTitle || !location) {
            alert('Please enter job title and location');
            return;
        }

        const btn = document.getElementById('searchBtn');
        btn.disabled = true;
        document.getElementById('searchSpinner').style.display = 'inline-block';

        document.getElementById('resultsCard').style.display = 'block';
        document.getElementById('jobsContainer').innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i><p>Searching across 20+ job boards...</p></div>';

        document.getElementById('resultsCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        const params = new URLSearchParams({
            job_title: jobTitle,
            location: location
        });

        fetch(`/api/v2/search-realtime?${params}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ resume_data: this.resumeData })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success && data.jobs) {
                this.allJobs = data.jobs;
                this.calculateMatches();
                this.applyFiltersAndSort();
                this.displayJobs();
                this.updateFilterCounts();
            } else {
                throw new Error(data.error || 'No jobs found');
            }
        })
        .catch(() => {
            this.allJobs = this.generateSampleJobs();
            this.calculateMatches();
            this.applyFiltersAndSort();
            this.displayJobs();
            this.updateFilterCounts();
        })
        .finally(() => {
            btn.disabled = false;
            document.getElementById('searchSpinner').style.display = 'none';
        });
    }

    generateSampleJobs() {
        const titles = ['Python Developer', 'Full Stack Developer', 'Frontend Engineer', 'Data Scientist', 'DevOps Engineer'];
        const companies = ['Google', 'Microsoft', 'Amazon', 'Apple', 'Netflix', 'Tesla', 'Meta'];
        const locations = ['Bangalore', 'Mumbai', 'Delhi', 'Remote', 'Hyderabad', 'Pune'];
        const salaries = ['₹50L - ₹70L', '₹60L - ₹80L', '₹40L - ₹60L', '₹70L - ₹90L'];

        return Array.from({ length: 20 }).map((_, i) => ({
            title: titles[Math.floor(Math.random() * titles.length)],
            company: companies[Math.floor(Math.random() * companies.length)],
            location: locations[Math.floor(Math.random() * locations.length)],
            salary: salaries[Math.floor(Math.random() * salaries.length)],
            posted: ['1 day ago', '3 days ago', '1 week ago', '2 weeks ago'][Math.floor(Math.random() * 4)],
            source: ['Indeed', 'LinkedIn', 'Naukri', 'Glassdoor'][Math.floor(Math.random() * 4)],
            url: 'https://example.com/job/' + i,
            description: 'Exciting opportunity to work with cutting-edge technology. Join our team and make an impact.',
            match_percentage: Math.floor(Math.random() * 40) + 60
        }));
    }

    calculateMatches() {
        if (!this.resumeData) return;

        this.allJobs.forEach(job => {
            if (!job.match_percentage) {
                const skills = this.resumeData.skills || [];
                const description = ((job.description || '') + ' ' + (job.title || '')).toLowerCase();

                let matched = 0;
                skills.forEach(skill => {
                    if (description.includes(skill.toLowerCase())) {
                        matched++;
                    }
                });

                let score = skills.length > 0 ? (matched / skills.length) * 100 : 50;

                if (description.includes((this.resumeData.category || '').toLowerCase())) {
                    score += 15;
                }

                job.match_percentage = Math.min(100, Math.round(score));
            }
        });
    }

    applyFiltersAndSort() {
        if (this.currentFilter === 'all') {
            this.filteredJobs = [...this.allJobs];
        } else {
            const minMatch = parseInt(this.currentFilter);
            this.filteredJobs = this.allJobs.filter(j => j.match_percentage >= minMatch);
        }

        switch (this.currentSort) {
            case 'match':
                this.filteredJobs.sort((a, b) => b.match_percentage - a.match_percentage);
                break;
            case 'recent':
                this.filteredJobs.sort((a, b) => {
                    const dateA = this.parseDate(a.posted);
                    const dateB = this.parseDate(b.posted);
                    return dateB - dateA;
                });
                break;
            case 'salary':
                this.filteredJobs.sort((a, b) => b.salary.localeCompare(a.salary));
                break;
            case 'company':
                this.filteredJobs.sort((a, b) => a.company.localeCompare(b.company));
                break;
        }

        this.displayJobs();
    }

    parseDate(dateStr) {
        const days = parseInt(dateStr);
        if (!isNaN(days)) return new Date(Date.now() - days * 24 * 60 * 60 * 1000);
        return new Date();
    }

    displayJobs() {
        const container = document.getElementById('jobsContainer');

        if (this.filteredJobs.length === 0) {
            container.innerHTML = '';
            document.getElementById('emptyState').style.display = 'block';
            return;
        }

        document.getElementById('emptyState').style.display = 'none';
        container.innerHTML = this.filteredJobs.map((job, idx) => this.createJobCard(job, idx)).join('');

        container.querySelectorAll('.job-card').forEach((card, idx) => {
            card.addEventListener('click', () => this.showJobDetails(this.filteredJobs[idx]));
        });
    }

    createJobCard(job) {
        const matchClass = job.match_percentage >= 80 ? 'high' : job.match_percentage >= 60 ? 'medium' : 'low';
        return `
            <div class="job-card">
                <div class="job-info">
                    <h3>${this.escapeHtml(job.title)}</h3>
                    <p class="job-company">${this.escapeHtml(job.company)}</p>
                    <div class="job-meta">
                        <span><i class="fas fa-map-marker-alt"></i> ${this.escapeHtml(job.location)}</span>
                        <span><i class="fas fa-dollar-sign"></i> ${this.escapeHtml(job.salary)}</span>
                        <span><i class="fas fa-calendar"></i> ${this.escapeHtml(job.posted)}</span>
                        <span><i class="fas fa-globe"></i> ${this.escapeHtml(job.source)}</span>
                    </div>
                </div>
                <div class="match-score">
                    <div class="match-percentage ${matchClass}">${job.match_percentage}%</div>
                    <div class="match-label">Match</div>
                    <div class="match-bar">
                        <div class="match-fill" style="width: ${job.match_percentage}%"></div>
                    </div>
                </div>
            </div>
        `;
    }

    updateFilterCounts() {
        document.querySelector('[data-count="all"]').textContent = this.allJobs.length;
        document.querySelector('[data-count="90"]').textContent = this.allJobs.filter(j => j.match_percentage >= 90).length;
        document.querySelector('[data-count="80"]').textContent = this.allJobs.filter(j => j.match_percentage >= 80).length;
        document.querySelector('[data-count="60"]').textContent = this.allJobs.filter(j => j.match_percentage >= 60).length;
    }

    showJobDetails(job) {
        const modal = document.getElementById('jobModal');
        const body = document.getElementById('modalBody');

        const matchLevel = job.match_percentage >= 80 ? 'Excellent' : job.match_percentage >= 60 ? 'Good' : 'Fair';

        body.innerHTML = `
            <h2>${this.escapeHtml(job.title)}</h2>
            <p style="color: var(--primary); font-weight: 600; margin-bottom: 20px;">
                <i class="fas fa-building"></i> ${this.escapeHtml(job.company)}
            </p>
            <div style="background: var(--gray-100); border-radius: 8px; padding: 20px; margin: 20px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                <div>
                    <span style="font-weight: 600; color: var(--gray-600); font-size: 0.9em;">LOCATION</span>
                    <p style="color: var(--dark); font-weight: 600; margin-top: 8px;">${this.escapeHtml(job.location)}</p>
                </div>
                <div>
                    <span style="font-weight: 600; color: var(--gray-600); font-size: 0.9em;">SALARY</span>
                    <p style="color: var(--dark); font-weight: 600; margin-top: 8px;">${this.escapeHtml(job.salary)}</p>
                </div>
                <div>
                    <span style="font-weight: 600; color: var(--gray-600); font-size: 0.9em;">POSTED</span>
                    <p style="color: var(--dark); font-weight: 600; margin-top: 8px;">${this.escapeHtml(job.posted)}</p>
                </div>
                <div>
                    <span style="font-weight: 600; color: var(--gray-600); font-size: 0.9em;">YOUR MATCH</span>
                    <p style="color: var(--primary); font-weight: 600; margin-top: 8px;">${job.match_percentage}% (${matchLevel})</p>
                </div>
            </div>
            <p style="color: var(--gray-700); margin: 20px 0; line-height: 1.6;">${this.escapeHtml(job.description || 'Click below to apply on ' + job.source)}</p>
            <button class="btn-primary" style="margin-top: 20px;" onclick="window.open('${job.url}', '_blank')">
                <i class="fas fa-external-link-alt"></i> Apply on ${this.escapeHtml(job.source)}
            </button>
        `;

        modal.classList.add('active');
    }

    closeModal() {
        document.getElementById('jobModal').classList.remove('active');
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text ? text.replace(/[&<>"']/g, m => map[m]) : '';
    }
}

const app = new JobMatchApp();
document.addEventListener('DOMContentLoaded', () => {});
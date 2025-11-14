from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from PyPDF2 import PdfReader
import re
import pickle
import nltk
from nltk import word_tokenize, pos_tag, ne_chunk
from nltk.tree import Tree
import unicodedata

# If first run, uncomment and run once
# nltk.download('punkt')
# nltk.download('averaged_perceptron_tagger')
# nltk.download('maxent_ne_chunker')
# nltk.download('words')

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# ===================== MODEL LOAD ==========================
rf_classifier_categorization = pickle.load(open('model/rf_classifier_categorization.pkl', 'rb'))
tfidf_vectorizer_categorization = pickle.load(open('model/tfidf_vectorizer_categorization.pkl', 'rb'))


# ===================== UTILITIES ===========================
def cleanResume(txt):
    cleanText = re.sub(r'http\S+\s', ' ', txt)
    cleanText = re.sub(r'RT|cc', ' ', cleanText)
    cleanText = re.sub(r'#\S+\s', ' ', cleanText)
    cleanText = re.sub(r'@\S+', ' ', cleanText)
    cleanText = re.sub(r'[%s]' % re.escape("""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""), ' ', cleanText)
    cleanText = re.sub(r'[^\x00-\x7f]', ' ', cleanText)
    cleanText = re.sub(r'\s+', ' ', cleanText)
    return cleanText.strip()



def pdf_to_text(file):
    reader = PdfReader(file)
    text = ''
    for page in range(len(reader.pages)):
        content = reader.pages[page].extract_text()
        if content:
            text += content + '\n'
    return text


# ===================== MODEL PREDICTIONS ===========================
def predict_category(resume_text):
    resume_text = cleanResume(resume_text)
    resume_tfidf = tfidf_vectorizer_categorization.transform([resume_text])
    return rf_classifier_categorization.predict(resume_tfidf)[0]


# ===================== PARSING HELPERS ===========================
def extract_name_from_resume(text):
    """
    Smart name extraction that works for:
    - two-column resumes
    - resumes where contact info is on same line as name
    - uppercase or mixed-case names
    - resumes where the name line contains noise
    """

    # Normalize lines
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Only look at first ~8 lines (where names usually are)
    top = lines[:8]

    # Remove lines that contain non-name stuff
    filtered = []
    for line in top:
        l = line.lower()
        if any(x in l for x in ["@", "email", "github", "linkedin", "phone", "+91", "contact", ".com"]):
            continue
        if re.search(r"\d", l):  # remove lines with digits
            continue
        filtered.append(line)

    # If filtering removed everything, use fallback
    if not filtered:
        filtered = top

    # Strategy 1 — Look for lines that look like names (2–4 alphabetic words)
    for line in filtered:
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.match(r"^[A-Za-z][A-Za-z\.\-']*$", w) for w in words):
            return " ".join(w.capitalize() for w in words)

    # Strategy 2 — Find longest alphabetic-only line
    alphabetic_lines = []
    for line in filtered:
        if re.match(r"^[A-Za-z \-\.']+$", line):
            alphabetic_lines.append(line)

    if alphabetic_lines:
        best = max(alphabetic_lines, key=len)
        words = best.split()
        if 1 <= len(words) <= 5:
            return " ".join(w.capitalize() for w in words)

    # Strategy 3 — Take first 2 alphabetic words from the very first line
    words = re.findall(r"[A-Za-z]+", lines[0])
    if len(words) >= 2:
        return words[0].capitalize() + " " + words[1].capitalize()

    # Strategy 4 — As last fallback, return first non-empty line
    return lines[0]

def extract_email_from_resume(text):
    match = re.search(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b', text)
    return match.group().strip() if match else None

def extract_contact_number_from_resume(text):
    """More permissive phone extraction:
       - Looks for lines with 'phone', 'tel', or common number formats
       - Returns cleaned version preserving country code if present
    """
    # Search for label-based phone first
    phone_label = re.search(r'(phone|tel|mobile|contact)[:\s]*([+\d\(\)\-\s\.]{7,})', text, re.I)
    if phone_label:
        candidate = phone_label.group(2)
        digits = re.sub(r'\D', '', candidate)
        if 7 <= len(digits) <= 15:
            # Return in readable format: original (trimmed)
            return candidate.strip()

    # Generic patterns
    patterns = [
        r'(\+?\d{1,3}[-\s\.]?\(?\d{2,4}\)?[-\s\.]?\d{3,4}[-\s\.]?\d{3,4})',  # flexible groups
        r'(\(?\d{3}\)?[-\s\.]?\d{3}[-\s\.]?\d{4})',  # (555) 345-6789 etc
        r'(\b\d{10}\b)',  # 10-digit
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            candidate = m.group(1)
            digits = re.sub(r'\D', '', candidate)
            if 7 <= len(digits) <= 15:
                return candidate.strip()
    return None

def get_section_text(text, header_names, stop_headers=None, window_chars=1500):
    if stop_headers is None:
        stop_headers = ['experience','work experience','skills','projects','certifications','publications']

    text_lower = text.lower()

    for header in header_names:
        idx = text_lower.find(header.lower())
        if idx != -1:
            start = idx + len(header)

            # Find nearest stop header
            stop_idx = len(text)
            for sh in stop_headers:
                sidx = text_lower.find(sh.lower(), start)
                if sidx != -1 and sidx < stop_idx:
                    stop_idx = sidx

            return text[start:stop_idx].strip()

    return None


# Full skill list (kept intact/expanded). If you want to keep the original huge list, paste it here.
FULL_SKILLS_LIST = [
        'Python', 'Data Analysis', 'Machine Learning', 'Communication', 'Project Management', 'Deep Learning', 'SQL',
        'Tableau',
        'Java', 'C++', 'JavaScript', 'HTML', 'CSS', 'React', 'Angular', 'Node.js', 'MongoDB', 'Express.js', 'Git',
        'Research', 'Statistics', 'Quantitative Analysis', 'Qualitative Analysis', 'SPSS', 'R', 'Data Visualization',
        'Matplotlib',
        'Seaborn', 'Plotly', 'Pandas', 'Numpy', 'Scikit-learn', 'TensorFlow', 'Keras', 'PyTorch', 'NLTK', 'Text Mining',
        'Natural Language Processing', 'Computer Vision', 'Image Processing', 'OCR', 'Speech Recognition',
        'Recommendation Systems',
        'Collaborative Filtering', 'Content-Based Filtering', 'Reinforcement Learning', 'Neural Networks',
        'Convolutional Neural Networks',
        'Recurrent Neural Networks', 'Generative Adversarial Networks', 'XGBoost', 'Random Forest', 'Decision Trees',
        'Support Vector Machines',
        'Linear Regression', 'Logistic Regression', 'K-Means Clustering', 'Hierarchical Clustering', 'DBSCAN',
        'Association Rule Learning',
        'Apache Hadoop', 'Apache Spark', 'MapReduce', 'Hive', 'HBase', 'Apache Kafka', 'Data Warehousing', 'ETL',
        'Big Data Analytics',
        'Cloud Computing', 'Amazon Web Services (AWS)', 'Microsoft Azure', 'Google Cloud Platform (GCP)', 'Docker',
        'Kubernetes', 'Linux',
        'Shell Scripting', 'Cybersecurity', 'Network Security', 'Penetration Testing', 'Firewalls', 'Encryption',
        'Malware Analysis',
        'Digital Forensics', 'CI/CD', 'DevOps', 'Agile Methodology', 'Scrum', 'Kanban', 'Continuous Integration',
        'Continuous Deployment',
        'Software Development', 'Web Development', 'Mobile Development', 'Backend Development', 'Frontend Development',
        'Full-Stack Development',
        'UI/UX Design', 'Responsive Design', 'Wireframing', 'Prototyping', 'User Testing', 'Adobe Creative Suite',
        'Photoshop', 'Illustrator',
        'InDesign', 'Figma', 'Sketch', 'Zeplin', 'InVision', 'Product Management', 'Market Research',
        'Customer Development', 'Lean Startup',
        'Business Development', 'Sales', 'Marketing', 'Content Marketing', 'Social Media Marketing', 'Email Marketing',
        'SEO', 'SEM', 'PPC',
        'Google Analytics', 'Facebook Ads', 'LinkedIn Ads', 'Lead Generation', 'Customer Relationship Management (CRM)',
        'Salesforce',
        'HubSpot', 'Zendesk', 'Intercom', 'Customer Support', 'Technical Support', 'Troubleshooting',
        'Ticketing Systems', 'ServiceNow',
        'ITIL', 'Quality Assurance', 'Manual Testing', 'Automated Testing', 'Selenium', 'JUnit', 'Load Testing',
        'Performance Testing',
        'Regression Testing', 'Black Box Testing', 'White Box Testing', 'API Testing', 'Mobile Testing',
        'Usability Testing', 'Accessibility Testing',
        'Cross-Browser Testing', 'Agile Testing', 'User Acceptance Testing', 'Software Documentation',
        'Technical Writing', 'Copywriting',
        'Editing', 'Proofreading', 'Content Management Systems (CMS)', 'WordPress', 'Joomla', 'Drupal', 'Magento',
        'Shopify', 'E-commerce',
        'Payment Gateways', 'Inventory Management', 'Supply Chain Management', 'Logistics', 'Procurement',
        'ERP Systems', 'SAP', 'Oracle',
        'Microsoft Dynamics', 'Tableau', 'Power BI', 'QlikView', 'Looker', 'Data Warehousing', 'ETL',
        'Data Engineering', 'Data Governance',
        'Data Quality', 'Master Data Management', 'Predictive Analytics', 'Prescriptive Analytics',
        'Descriptive Analytics', 'Business Intelligence',
        'Dashboarding', 'Reporting', 'Data Mining', 'Web Scraping', 'API Integration', 'RESTful APIs', 'GraphQL',
        'SOAP', 'Microservices',
        'Serverless Architecture', 'Lambda Functions', 'Event-Driven Architecture', 'Message Queues', 'GraphQL',
        'Socket.io', 'WebSockets'
                     'Ruby', 'Ruby on Rails', 'PHP', 'Symfony', 'Laravel', 'CakePHP', 'Zend Framework', 'ASP.NET', 'C#',
        'VB.NET', 'ASP.NET MVC', 'Entity Framework',
        'Spring', 'Hibernate', 'Struts', 'Kotlin', 'Swift', 'Objective-C', 'iOS Development', 'Android Development',
        'Flutter', 'React Native', 'Ionic',
        'Mobile UI/UX Design', 'Material Design', 'SwiftUI', 'RxJava', 'RxSwift', 'Django', 'Flask', 'FastAPI',
        'Falcon', 'Tornado', 'WebSockets',
        'GraphQL', 'RESTful Web Services', 'SOAP', 'Microservices Architecture', 'Serverless Computing', 'AWS Lambda',
        'Google Cloud Functions',
        'Azure Functions', 'Server Administration', 'System Administration', 'Network Administration',
        'Database Administration', 'MySQL', 'PostgreSQL',
        'SQLite', 'Microsoft SQL Server', 'Oracle Database', 'NoSQL', 'MongoDB', 'Cassandra', 'Redis', 'Elasticsearch',
        'Firebase', 'Google Analytics',
        'Google Tag Manager', 'Adobe Analytics', 'Marketing Automation', 'Customer Data Platforms', 'Segment',
        'Salesforce Marketing Cloud', 'HubSpot CRM',
        'Zapier', 'IFTTT', 'Workflow Automation', 'Robotic Process Automation (RPA)', 'UI Automation',
        'Natural Language Generation (NLG)',
        'Virtual Reality (VR)', 'Augmented Reality (AR)', 'Mixed Reality (MR)', 'Unity', 'Unreal Engine', '3D Modeling',
        'Animation', 'Motion Graphics',
        'Game Design', 'Game Development', 'Level Design', 'Unity3D', 'Unreal Engine 4', 'Blender', 'Maya',
        'Adobe After Effects', 'Adobe Premiere Pro',
        'Final Cut Pro', 'Video Editing', 'Audio Editing', 'Sound Design', 'Music Production', 'Digital Marketing',
        'Content Strategy', 'Conversion Rate Optimization (CRO)',
        'A/B Testing', 'Customer Experience (CX)', 'User Experience (UX)', 'User Interface (UI)', 'Persona Development',
        'User Journey Mapping', 'Information Architecture (IA)',
        'Wireframing', 'Prototyping', 'Usability Testing', 'Accessibility Compliance', 'Internationalization (I18n)',
        'Localization (L10n)', 'Voice User Interface (VUI)',
        'Chatbots', 'Natural Language Understanding (NLU)', 'Speech Synthesis', 'Emotion Detection',
        'Sentiment Analysis', 'Image Recognition', 'Object Detection',
        'Facial Recognition', 'Gesture Recognition', 'Document Recognition', 'Fraud Detection',
        'Cyber Threat Intelligence', 'Security Information and Event Management (SIEM)',
        'Vulnerability Assessment', 'Incident Response', 'Forensic Analysis', 'Security Operations Center (SOC)',
        'Identity and Access Management (IAM)', 'Single Sign-On (SSO)',
        'Multi-Factor Authentication (MFA)', 'Blockchain', 'Cryptocurrency', 'Decentralized Finance (DeFi)',
        'Smart Contracts', 'Web3', 'Non-Fungible Tokens (NFTs)',
        # Culinary Chef
    "Cooking", "Food Preparation", "Menu Planning", "Food Safety", "Hygiene",
    "Baking", "Knife Skills", "Inventory Management", "Plating", "Presentation",
    "Recipe Development", "Team Leadership",
    
    # Elementary School Teacher
    "Lesson Planning", "Classroom Management", "Curriculum Development", "Student Assessment",
    "Communication Skills", "Educational Technology", "Creativity", "Storytelling",
    "Conflict Resolution", "Child Engagement",
    
    # Executive Assistant
    "Calendar Management", "Scheduling", "Email Management", "Travel Planning",
    "Communication Skills", "Report Preparation", "Event Coordination", "Organization",
    "MS Office", "Google Suite", "Multitasking",
    
    # Registered Nurse
    "Patient Care", "Vital Signs Monitoring", "Medication Administration", "Emergency Response",
    "Wound Care", "Health Assessment", "Medical Documentation", "Communication Skills",
    "Teamwork", "Clinical Procedures"
]

def extract_skills_from_resume(text, name=None):
    """
    Extract skills but ignore the top header where name/contact typically appears,
    and also remove any skills that accidentally match the candidate's name.
    """
    lines = text.strip().split('\n')
    # ignore top lines (first 6) to avoid name leaking in skills
    body = '\n'.join(lines[6:]) if len(lines) > 6 else text

    found = []
    for skill in FULL_SKILLS_LIST:
        # use word boundary match to reduce partial matches
        if re.search(r'\b' + re.escape(skill) + r'\b', body, re.IGNORECASE):
            found.append(skill)

    # Remove any found that are part of the candidate name
    if name:
        for token in name.split():
            found = [s for s in found if token.lower() not in s.lower()]

    # Final cleaning: unique, preserve original casing from list
    unique_found = []
    for s in FULL_SKILLS_LIST:
        if s in found and s not in unique_found:
            unique_found.append(s)
    return unique_found

# ===================== EDUCATION EXTRACTION ===========================
# Degree normalization map (regex pattern -> normalized label)
DEGREE_PATTERNS = {
    r'\bbachelor of technology\b': 'B.Tech',
    r'\bb\.?\s*tech\b': 'B.Tech',
    r'\bbachelor of engineering\b': 'B.E',
    r'\bb\.?\s*e\b': 'B.E',
    r'\bbachelor of science\b': 'B.Sc',
    r'\bb\.?\s*sc\b': 'B.Sc',
    r'\bbachelor of arts\b': 'B.A',
    r'\bb\.?\s*a\b': 'B.A',
    r'\bbachelor of commerce\b': 'B.Com',
    r'\bb\.?\s*com\b': 'B.Com',
    r'\bbachelor of computer applications\b': 'BCA',
    r'\bb\.?\s*c\.?a\b': 'BCA',
    r'\bbachelor of business administration\b': 'BBA',
    r'\bb\.?\s*b\.?\s*a\b': 'BBA',

    # Masters
    r'\bmaster of technology\b': 'M.Tech',
    r'\bm\.?\s*tech\b': 'M.Tech',
    r'\bmaster of science\b': 'M.Sc',
    r'\bm\.?\s*sc\b': 'M.Sc',
    r'\bmaster of business administration\b': 'MBA',
    r'\bm\.?\s*b\.?\s*a\b': 'MBA',
    r'\bmaster of engineering\b': 'M.E',
    r'\bm\.?\s*e\b': 'M.E',
    r'\bmaster of computer applications\b': 'MCA',
    r'\bm\.?\s*c\.?\s*a\b': 'MCA',

    # Diplomas
    r'\bpg diploma\b': 'PG Diploma',
    r'\bpost[- ]graduate diploma\b': 'PG Diploma',
    r'\bdiploma\b': 'Diploma',

    # Doctorate
    r'\bph\.?\s*d\b': 'Ph.D',
    r'\bp\.?\s*hd\b': 'Ph.D',

    # Medical
    r'\bmbbs\b': 'MBBS',
}

# fields list (common fields)
FIELD_KEYWORDS = [
    # 🧑‍💻 Computer Science & IT
    'Computer Science', 'Information Technology', 'Software Engineering', 'Computer Engineering',
    'Artificial Intelligence', 'Machine Learning', 'Deep Learning', 'Data Science', 'Data Analytics',
    'Data Engineering', 'Big Data Analytics', 'Cloud Computing', 'Cybersecurity', 'Information Security',
    'Network Security', 'Blockchain Technology', 'Internet of Things (IoT)', 'Web Development',
    'Mobile App Development', 'Game Development', 'Virtual Reality', 'Augmented Reality',
    'Human-Computer Interaction', 'Digital Forensics', 'Robotics', 'Automation',

    # ⚙️ Engineering & Technology
    'Electrical Engineering', 'Electronics Engineering', 'Electronics and Communication Engineering',
    'Mechanical Engineering', 'Civil Engineering', 'Chemical Engineering', 'Aerospace Engineering',
    'Automotive Engineering', 'Industrial Engineering', 'Instrumentation Engineering', 'Mechatronics Engineering',
    'Systems Engineering', 'Environmental Engineering', 'Biomedical Engineering', 'Marine Engineering',
    'Petroleum Engineering', 'Structural Engineering', 'Metallurgical Engineering', 'Textile Engineering',
    'Production Engineering', 'Power Engineering', 'Nanotechnology',

    # 📊 Business, Management & Finance
    'Business Administration', 'Management', 'Finance', 'Accounting', 'Banking', 'Economics', 'Commerce',
    'Marketing', 'Human Resource Management', 'Supply Chain Management', 'Logistics', 'Operations Management',
    'Project Management', 'International Business', 'Entrepreneurship', 'Business Analytics',
    'Investment Management', 'Risk Management', 'Corporate Finance', 'Taxation', 'Actuarial Science',

    # 🧠 Science & Mathematics
    'Physics', 'Chemistry', 'Mathematics', 'Statistics', 'Applied Mathematics', 'Environmental Science',
    'Earth Science', 'Geology', 'Oceanography', 'Meteorology', 'Astronomy', 'Biophysics', 'Biochemistry',
    'Microbiology', 'Molecular Biology', 'Biotechnology', 'Zoology', 'Botany', 'Genetics', 'Life Sciences',
    'Nanoscience', 'Forensic Science', 'Agricultural Science', 'Food Technology', 'Horticulture', 'Forestry',

    # 🩺 Medical & Health Sciences
    'Medicine', 'Dentistry', 'Pharmacy', 'Nursing', 'Physiotherapy', 'Public Health', 'Biomedical Science',
    'Veterinary Science', 'Nutrition and Dietetics', 'Occupational Therapy', 'Radiology', 'Pathology',
    'Anatomy', 'Physiology', 'Medical Microbiology', 'Epidemiology', 'Paramedical Science', 'Ayurveda',
    'Homeopathy', 'Medical Technology',

    # 🧬 Life Sciences & Biological Sciences
    'Biology', 'Biotechnology', 'Bioinformatics', 'Biostatistics', 'Marine Biology', 'Ecology',
    'Environmental Biology', 'Genetics', 'Immunology', 'Molecular Biology', 'Neuroscience', 'Pharmacology',
    'Toxicology',

    # 🧑‍🏫 Education, Arts & Humanities
    'Education', 'Teaching', 'Psychology', 'Sociology', 'Political Science', 'Public Administration',
    'History', 'Geography', 'Philosophy', 'Anthropology', 'Archaeology', 'Library Science', 'Linguistics',
    'English Literature', 'Foreign Languages', 'Journalism', 'Mass Communication', 'Fine Arts',
    'Performing Arts', 'Visual Arts', 'Graphic Design', 'Animation', 'Film Studies', 'Music', 'Theatre',
    'Creative Writing', 'Cultural Studies',

    # 🧱 Architecture, Design & Planning
    'Architecture', 'Interior Design', 'Urban Planning', 'Landscape Architecture', 'Construction Management',
    'Structural Design', 'Industrial Design', 'Product Design', 'Fashion Design', 'Textile Design',
    'User Experience Design', 'User Interface Design',

    # ⚖️ Law, Policy & Governance
    'Law', 'Constitutional Law', 'International Law', 'Corporate Law', 'Criminal Law', 'Human Rights Law',
    'Political Science', 'Public Policy', 'Governance', 'Criminology', 'Forensic Investigation',
    'Defense Studies', 'Security Studies',

    # 🌍 Social Sciences & Development Studies
    'Economics', 'Development Studies', 'Social Work', 'Gender Studies', 'International Relations',
    'Rural Development', 'Urban Studies', 'Demography', 'Peace and Conflict Studies',

    # 💼 Emerging & Interdisciplinary Fields
    'Artificial Intelligence and Robotics', 'Cognitive Science', 'Sustainability Studies', 'Climate Science',
    'Renewable Energy', 'Disaster Management', 'Energy Systems', 'Human Factors Engineering',
    'Digital Transformation', 'Industrial Automation', 'FinTech', 'Health Informatics', 'Sports Science',
    'Behavioral Economics'
    
    # Culinary Chef
    "Culinary Arts", "Professional Cooking", "Gastronomy", "Food Science",
    "Baking and Pastry", "Hospitality Management", "Chef Certification",
    
    # Elementary School Teacher
    "Bachelor of Education", "B.Ed", "Elementary Education", "Early Childhood Education",
    "Teaching Certification", "Child Development",
    
    # Executive Assistant
    "Business Administration", "Office Management", "Secretarial Studies",
    "Management Studies", "Administrative Studies", "Certified Administrative Professional", "CAP",
    
    # Registered Nurse
    "Nursing", "Bachelor of Science in Nursing", "B.Sc Nursing", "Associate Degree in Nursing", "ADN",
    "Diploma in Nursing", "RN License", "Registered Nurse", "Nursing Certification", "BLS", "ACLS"
]

INSTITUTION_PATTERNS = [r'\bUniversity\b', r'\bInstitute\b', r'\bCollege\b', r'\bSchool\b', r'\bInstitute of\b', r'\bUniversity of\b']

def clean_pdf_text(text):
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()
# ----------------------------
# Fuzzy header detection
# ----------------------------
def fuzzy_header_regex(header):
    return r"\s*".join(list(header.strip()))

def get_section_text(text, header_names, stop_headers=None, window_chars=900):
    if stop_headers is None:
        stop_headers = [
            'experience', 'work experience', 'professional experience',
            'skills', 'projects', 'certifications', 'achievements',
            'publications', 'internships'
        ]

    text_clean = clean_pdf_text(text.lower())

    # Try to locate header using fuzzy search
    for header in header_names:
        pattern = r"\b" + fuzzy_header_regex(header.lower()) + r"\b"
        match = re.search(pattern, text_clean, re.I)
        if match:
            start = match.end()

            stop_pos = len(text_clean)
            for sh in stop_headers:
                sh_pat = r"\b" + fuzzy_header_regex(sh.lower()) + r"\b"
                m2 = re.search(sh_pat, text_clean[start:], re.I)
                if m2:
                    pos = start + m2.start()
                    if pos < stop_pos:
                        stop_pos = pos

            slice_end = min(stop_pos, start + window_chars)
            return text[start:slice_end]

    return None

# ----------------------------
# Normalize Degree
# ----------------------------
def normalize_degree_from_text(s):
    s_lower = s.lower()
    for pat, label in DEGREE_PATTERNS.items():
        if re.search(pat, s_lower, re.I):
            return label
    return None

# ----------------------------
# Extract Institution
# ----------------------------
def extract_institution(entry_clean):
    """
    Extract academic institutions reliably from education blocks.
    Works for long names, multi-word names, and names before OR after degree.
    """

    patterns = [
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}College of [A-Za-z\s]+",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}Institute of [A-Za-z\s]+",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}University of [A-Za-z\s]+",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}University\b",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}College\b",
        r"[A-Z][A-Za-z0-9&\.,\-\s]{4,}Institute\b",
        r"IIT [A-Za-z]+",
        r"NIT [A-Za-z]+",
        r"BITS [A-Za-z]+",
    ]

    # First, search for full institution name patterns
    for pat in patterns:
        m = re.search(pat, entry_clean, re.I)
        if m:
            return m.group(0).strip(" ,.-")

    # SECOND PASS → handle cases where the institution is BEFORE the degree block
    words = entry_clean.split()
    for i in range(len(words) - 2):
        chunk = " ".join(words[i:i+5])
        if any(kw in chunk.lower() for kw in ["college", "university", "institute", "school"]):
            return chunk.strip(" ,.-")

    return None


def fix_broken_pdf_lines(text):
    """
    PDFs sometimes break every word into its own line.
    This fixes that by joining short lines into full sentences.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    combined = []
    buffer = ""

    for line in lines:
        # If the line is very short (1–2 words), append to buffer
        if len(line.split()) <= 2:
            buffer += " " + line
        else:
            # If buffer has content, flush it
            if buffer.strip():
                combined.append(buffer.strip())
                buffer = ""
            combined.append(line)

    # Flush remaining buffer
    if buffer.strip():
        combined.append(buffer.strip())

    return "\n".join(combined)


# ----------------------------
# MAIN FUNCTION: extract_education_from_resume()
# ----------------------------
def extract_education_from_resume(text):

    # Get education section
    section = get_section_text(text, ['education', 'educational qualification', 'academic qualification'])

    if not section:
        section = text

    # Split into degree-based chunks
    chunks = re.split(r'(?<!\w)(Bachelor|Master|B\.|M\.)', section, flags=re.I)
    merged = []
    for i in range(1, len(chunks), 2):
        merged.append(chunks[i] + chunks[i+1])

    if not merged:
        merged = [section]

    results = []
    seen = set()

    for entry in merged:

        # Clean entry
        entry_clean = " ".join(entry.split())

        # -------- Fix broken PDF words --------
        entry_clean = re.sub(r"Machine\s+Le(?!arning)", "Machine Learning", entry_clean, flags=re.I)
        entry_clean = re.sub(
            r"Artificial\s+Intelligence\s*(?:&|and)?\s*Machine",
            "Artificial Intelligence and Machine",
            entry_clean,
            flags=re.I
        )

        # -------- Detect degree --------
        degree = normalize_degree_from_text(entry_clean)
        if not degree:
            continue

        # -------- Detect field --------
        invalid_field_words = ["technology"]   # avoid picking "Technology" from "Bachelor of Technology"
        field = None

        # CASE 1 — explicit "in field"
        m_field = re.search(r'\b(?:in|of)\s+([A-Za-z &\.\-\/]{2,60})', entry_clean, re.I)
        if m_field:
            field_candidate = m_field.group(1).strip(" ,.")
            field = field_candidate

        else:
            # CASE 2 — match keywords
            for fk in FIELD_KEYWORDS:
                fk_low = fk.lower()
                if fk_low in entry_clean.lower() and fk_low not in invalid_field_words:
                    field = fk.title()
                    break

        # -------- Detect institution --------
        inst = extract_institution(entry_clean)

        # If institution TEXT appears BEFORE the degree text, discard it
        # (It likely belongs to 12th/10th qualification)
        if inst:
            degree_pos = entry_clean.lower().find(degree.lower())
            inst_pos = entry_clean.lower().find(inst.lower())
            if inst_pos < degree_pos:
                inst = None

        # -------- Detect year --------
        year = None
        y = re.search(r'(19|20)\d{2}', entry_clean)
        if y:
            year = y.group()

        # -------- Build final string --------
        final = degree
        if field:
            final += f" in {field}"
        if inst:
            final += f" | {inst}"
        if year:
            final += f" ({year})"

        # -------- Deduplicate --------
        key = final.lower()
        if key not in seen:
            seen.add(key)
            results.append(final)

    return results if results else None

# ===================== FASTAPI ROUTES ===========================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("resumes.html", {"request": request})


@app.post("/pred", response_class=HTMLResponse)
async def pred(request: Request, resume: UploadFile = File(...)):
    filename = resume.filename

    if filename.lower().endswith(".pdf"):
        text = pdf_to_text(resume.file)
    elif filename.lower().endswith(".txt"):
        text = (await resume.read()).decode("utf-8")
    else:
        return templates.TemplateResponse("resumes.html", {
            "request": request,
            "message": "Invalid file format. Please upload PDF or TXT."
        })

    predicted_category = predict_category(text)

    name = extract_name_from_resume(text)
    email = extract_email_from_resume(text)
    phone = extract_contact_number_from_resume(text)
    extracted_education = extract_education_from_resume(text)
    extracted_skills = extract_skills_from_resume(text, name=name)

    return templates.TemplateResponse("resumes.html", {
        "request": request,
        "predicted_category": predicted_category,
        "name": name,
        "email": email,
        "phone": phone,
        "extracted_skills": extracted_skills,
        "extracted_education": extracted_education
    })


@app.post("/api/parse")
async def api_parse(resume: UploadFile = File(...)):
    filename = resume.filename

    if filename.lower().endswith(".pdf"):
        text = pdf_to_text(resume.file)
    elif filename.lower().endswith(".txt"):
        text = (await resume.read()).decode("utf-8")
    else:
        return JSONResponse({"error": "Invalid file format. Upload PDF or TXT."})

    predicted_category = predict_category(text)

    name = extract_name_from_resume(text)
    email = extract_email_from_resume(text)
    phone = extract_contact_number_from_resume(text)
    extracted_education = extract_education_from_resume(text)
    extracted_skills = extract_skills_from_resume(text, name=name)

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "category": predicted_category,
        "skills": extracted_skills,
        "education": extracted_education
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



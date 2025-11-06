from flask import Flask, request, render_template
from PyPDF2 import PdfReader
import re
import pickle
import nltk
from nltk import word_tokenize, pos_tag, ne_chunk
from nltk.tree import Tree

from flask import jsonify

# If running first time, uncomment and run these once:
# nltk.download('punkt')
# nltk.download('averaged_perceptron_tagger')
# nltk.download('maxent_ne_chunker')
# nltk.download('words')

app = Flask(__name__)

# ===================== MODEL LOAD ==========================
rf_classifier_categorization = pickle.load(open('model/rf_classifier_categorization.pkl', 'rb'))
tfidf_vectorizer_categorization = pickle.load(open('model/tfidf_vectorizer_categorization.pkl', 'rb'))

# ===================== UTILITIES ===========================
def cleanResume(txt):
    """Clean resume text for model and parsing"""
    cleanText = re.sub('http\S+\s', ' ', txt)
    cleanText = re.sub('RT|cc', ' ', cleanText)
    cleanText = re.sub('#\S+\s', ' ', cleanText)
    cleanText = re.sub('@\S+', ' ', cleanText)
    cleanText = re.sub('[%s]' % re.escape("""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"""), ' ', cleanText)
    cleanText = re.sub(r'[^\x00-\x7f]', ' ', cleanText)
    cleanText = re.sub('\s+', ' ', cleanText)
    return cleanText.strip()

def pdf_to_text(file):
    """Extract text from PDF (preserves line breaks where possible)"""
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
    """Extract candidate name using NER and regex fallback"""
    lines = text.strip().split('\n')
    lines = [l.strip() for l in lines if l.strip()]
    top_section = ' '.join(lines[:6])
    try:
        tokens = word_tokenize(top_section)
        tagged = pos_tag(tokens)
        chunked = ne_chunk(tagged)
    except Exception:
        chunked = []

    person_names = []
    for chunk in chunked:
        if isinstance(chunk, Tree) and chunk.label() == 'PERSON':
            name = ' '.join(c[0] for c in chunk.leaves())
            # Allow 2-4 token names
            if 2 <= len(name.split()) <= 4:
                person_names.append(name)

    if person_names:
        return person_names[0].strip()

    # Fallback regex: capitalized words at very top of resume (first 6 lines)
    for line in lines[:6]:
        # avoid lines that say "Resume", "Curriculum Vitae", "Contact"
        if re.search(r'resume|curriculum|vitae|cv|contact', line, re.I):
            continue
        match = re.match(r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,3})$', line)
        if match:
            return match.group().strip()
    return None

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

def get_section_text(text, header_names, stop_headers=None, window_chars=800):
    """
    Return text following the first occurrence of any header_name (case-insensitive),
    up to a stop header or a maximum window.
    """
    if stop_headers is None:
        stop_headers = ['experience', 'professional experience', 'work experience', 'skills', 'certifications', 'projects', 'objective', 'summary']

    lower = text.lower()
    for header in header_names:
        idx = lower.find(header.lower())
        if idx != -1:
            # start after the header word
            start = idx + len(header)
            # find nearest stop header after start
            stop_idx = len(text)
            for s in stop_headers:
                sidx = lower.find(s.lower(), start)
                if sidx != -1 and sidx < stop_idx:
                    stop_idx = sidx
            # slice a safe window
            slice_end = min(stop_idx, start + window_chars)
            return text[start:slice_end].strip()
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
    r'\b(b\.?\s*tech|bachelor\s*of\s*technology)\b': 'B.Tech',
    r'\b(b\.?\s*e|bachelor\s*of\s*engineering)\b': 'B.E.',
    r'\b(b\.?\s*sc|bachelor\s*of\s*science)\b': 'B.Sc.',
    r'\b(b\.?\s*a|bachelor\s*of\s*arts)\b': 'B.A.',
    r'\b(b\.?\s*com|bachelor\s*of\s*commerce|b\.?\s*b\.?a)\b': 'B.B.A./B.Com',
    r'\b(bca|b\.?\s*c\.?a)\b': 'BCA',
    r'\b(m\.?\s*tech|master\s*of\s*technology)\b': 'M.Tech',
    r'\b(m\.?\s*e|master\s*of\s*engineering)\b': 'M.E.',
    r'\b(m\.?\s*s|m\.?\s*sc|master\s*of\s*science)\b': 'M.Sc./M.S.',
    r'\b(mba|m\.?\s*b\.?a|master\s*of\s*business\s*administration)\b': 'MBA',
    r'\b(mca|m\.?\s*c\.?a)\b': 'MCA',
    r'\b(ph\.?\s*d|doctorate|phd)\b': 'Ph.D.',
    r'\b(diploma|certificate)\b': 'Diploma/Certificate',
    r'\b(high school|secondary|10th|12th|senior secondary)\b': 'School'
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

def normalize_degree_from_text(s):
    """Try to find a normalized degree label from text snippet s"""
    s_lower = s.lower()
    for pat, label in DEGREE_PATTERNS.items():
        if re.search(pat, s_lower, re.I):
            return label
    # Additionally detect short forms like 'ms in finance' -> 'M.Sc./M.S.'
    if re.search(r'\bms\b', s_lower) and 'finance' in s_lower:
        return 'M.Sc./M.S.'
    return None

def extract_institution(candidate):
    """Try to extract institution name from candidate string if present"""
    # Look for " | University..." or "University of X" or ", Northwestern University"
    # Return the institution substring cleaned
    for pat in INSTITUTION_PATTERNS:
        m = re.search(r'([A-Z][A-Za-z&\.\s\-\,]{3,}'+pat.replace(r'\b','')+')', candidate)
        if m:
            inst = m.group(0).strip(' ,|')
            return re.sub(r'\s{2,}',' ', inst)
    # fallback: look for capitalized phrase after '|' or after degree
    if '|' in candidate:
        parts = [p.strip() for p in candidate.split('|') if p.strip()]
        # choose last part if it has capital letter and length > 3
        if len(parts) > 1 and re.search(r'[A-Z]', parts[-1]) and len(parts[-1]) > 3:
            return parts[-1]
    return None

def extract_education_from_resume(text):
    """
    Extract education entries by:
    1) locating an 'Education' section and parsing lines from it, or
    2) scanning the whole text with stricter patterns if section not found.
    Returns a list of friendly strings like "M.S. in Finance | Northwestern University (2017)"
    """
    raw_section = get_section_text(text, header_names=['education', 'academic qualifications', 'educational qualifications'], stop_headers=['professional experience','work experience','skills','certifications','projects','publications'])

    candidates = []
    if raw_section:
        # split candidate entries by separators frequently used in resumes
        pieces = re.split(r'\n|\r|;|·|•|\|| -{2,} | – | — |, (?=[A-Z])', raw_section)
        for p in pieces:
            p = p.strip()
            if len(p) >= 4:
                candidates.append(p)
    else:
        # fallback: search the whole text for degree patterns and capture surrounding words (up to 80 chars)
        for pat in DEGREE_PATTERNS.keys():
            for m in re.finditer(pat, text, re.I):
                start = max(0, m.start()-50)
                end = min(len(text), m.end()+100)
                snippet = text[start:end].strip()
                candidates.append(snippet)

    results = []
    seen = set()
    for cand in candidates:
        cand_clean = re.sub(r'\s+', ' ', cand).strip()
        # Avoid generic lines that are obviously not education
        if len(cand_clean) < 4 or re.search(r'project|internship|certificat|responsibilit|experience|objective|summary|skills', cand_clean, re.I):
            continue

        degree_label = normalize_degree_from_text(cand_clean)
        # Try to extract field (explicit 'in <field>' or known field keywords)
        field = None
        m_field = re.search(r'\b(?:in|of)\s+([A-Za-z &\.\-\/]{2,40})', cand_clean, re.I)
        if m_field:
            candidate_field = m_field.group(1).strip(' ,.')
            # check if candidate_field contains one of the known fields
            for fk in FIELD_KEYWORDS:
                if fk in candidate_field.lower() or fk in cand_clean.lower():
                    field = candidate_field.title()
                    break
            if not field:
                # still accept it if it's reasonably short and alphabetic
                if 2 <= len(candidate_field) <= 30 and re.search(r'[A-Za-z]', candidate_field):
                    field = candidate_field.title()
        else:
            # search known field keywords
            for fk in FIELD_KEYWORDS:
                if fk in cand_clean.lower():
                    field = fk.title()
                    break

        institution = extract_institution(cand_clean)
        # Extract year if present
        year_match = re.search(r'\b(19|20)\d{2}\b', cand_clean)
        year = year_match.group(0) if year_match else None

        # Build normalized entry
        entries = []
        if degree_label:
            if field:
                entries.append(f"{degree_label} in {field}")
            else:
                entries.append(degree_label)
        elif field:
            entries.append(field)

        if not entries:
            # nothing useful found; skip
            continue

        # Compose final string
        final = entries[0]
        if institution:
            final = f"{final} | {institution}"
        if year:
            final = f"{final} ({year})"

        # de-dup
        final_norm = final.lower()
        if final_norm not in seen:
            seen.add(final_norm)
            results.append(final)

    return results if results else None

# ===================== FLASK ROUTES ===========================
@app.route('/')
def resume():
    return render_template("resumes.html")

@app.route('/pred', methods=['POST'])
def pred():
    if 'resume' in request.files:
        file = request.files['resume']
        filename = file.filename
        if filename.lower().endswith('.pdf'):
            text = pdf_to_text(file)
        elif filename.lower().endswith('.txt'):
            text = file.read().decode('utf-8')
        else:
            return render_template('resumes.html', message="Invalid file format. Please upload PDF or TXT.")

        # predictions (unchanged)
        predicted_category = predict_category(text)

        # parsing
        name = extract_name_from_resume(text)
        email = extract_email_from_resume(text)
        phone = extract_contact_number_from_resume(text)
        extracted_education = extract_education_from_resume(text)
        extracted_skills = extract_skills_from_resume(text, name=name)

        return render_template(
            'resumes.html',
            predicted_category=predicted_category,
            name=name,
            email=email,
            phone=phone,
            extracted_skills=extracted_skills,
            extracted_education=extracted_education
        )

    return render_template("resumes.html", message="No file uploaded.")

# JSON results
@app.route('/api/parse', methods=['POST'])
def api_parse():
    if 'resume' in request.files:
        file = request.files['resume']
        filename = file.filename
        if filename.lower().endswith('.pdf'):
            text = pdf_to_text(file)
        elif filename.lower().endswith('.txt'):
            text = file.read().decode('utf-8')
        else:
            return render_template('resumes.html', message="Invalid file format. Please upload PDF or TXT.")

        # predictions (unchanged)
        predicted_category = predict_category(text)

        # parsing
        name = extract_name_from_resume(text)
        email = extract_email_from_resume(text)
        phone = extract_contact_number_from_resume(text)
        extracted_education = extract_education_from_resume(text)
        extracted_skills = extract_skills_from_resume(text, name=name)
    
    return jsonify({
        'name': name,
        'email': email,
        'phone': phone,
        'category': predicted_category,
        'skills': extracted_skills,
        'education': extracted_education
    })

if __name__ == '__main__':
    app.run(debug=True)

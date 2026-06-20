# 🏥 Health Vault

## 🔗 Live Demo

https://health-vault-ylmr.onrender.com/

---

## 📌 Overview

Health Vault is an AI-powered secure medical record management system that allows patients to store, manage, analyze, and securely share medical reports with healthcare professionals.

The platform combines secure report storage, AI-powered report summarization, machine learning-based disease prediction, and intelligent report retrieval to improve medical data accessibility while maintaining patient privacy.

---

## 🚀 Features

### 👤 Patients

    * Register & Login
    * Upload and manage medical reports
    * Categorize reports
    * Generate temporary access keys
    * Selective report sharing
    * QR-based report access sharing
    * View uploaded reports
    * AI-powered disease prediction
    * Smart report recommendations based on symptoms and disease prediction

### 🩺 Doctors

    * Access patient reports using temporary access keys
    * QR-code based report access
    * Read-only report viewing
    * AI-generated report summaries

### 🤖 AI Features

#### AI Report Summarization

    * Extracts text from uploaded medical reports
    * Uses OCR for scanned reports
    * Generates AI-powered medical summaries using Groq LLM
    * Stores summaries for future retrieval

#### Smart Medical Report Retrieval

Workflow:

    Symptoms
    ↓
    Disease Prediction
    ↓
    Retrieve Patient Report Summaries
    ↓
    AI Analysis
    ↓
    Rank Relevant Reports
    ↓
    Auto-Select Reports for Sharing

    The system automatically identifies the most relevant reports for the predicted disease and recommends them before report sharing.

### 🧠 Machine Learning Features

#### Disease Prediction

* Random Forest Classifier
* 132 symptom inputs
* 41 disease classes
* Top 3 disease predictions
* Confidence scores for each prediction
* Trained using medical symptom datasets

Example:

Symptoms:

* Itching
* Skin Rash

Prediction:

1. Fungal Infection – 57%
2. Drug Reaction – 21.5%
3. Acne – 5%

---

## 🔒 Security

    * Temporary access keys
    * QR-based secure sharing
    * Patient-controlled report access
    * Session-based authentication
    * Privacy-focused report sharing
    * Secure local storage using SQLite

---

## 🛠️ Tech Stack

### Backend

* Flask
* Python

### Database

* SQLite

### AI

* Groq LLM
* OCR (PyTesseract)
* PDF Text Extraction

### Machine Learning

* Scikit-Learn
* Random Forest Classifier
* Joblib

### Frontend

* HTML
* CSS
* JavaScript

### Deployment

* Render

---

## ⚙️ Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Run application:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## 💡 Use Cases

* Secure medical report storage
* Smart report retrieval
* Disease prediction assistance
* Temporary doctor access
* Healthcare data management

---

## 📂 Project Structure

```text
app.py
services/
│
├── smart_report_retrieval.py

ml/
├── train_model.py
├── predict.py
├── service.py
├── models/
│   ├── disease_model.pkl
│   ├── feature_names.pkl
│   └── label_encoder.pkl

uploads/
health_vault.db
```

---

## 📸 Screenshots

<img width="1503" height="905" alt="pic1" src="https://github.com/user-attachments/assets/c80c2792-ea95-4bc7-8fd1-6e9def211ce1" />

<img width="1445" height="887" alt="Screenshot 2026-06-20 194714" src="https://github.com/user-attachments/assets/f56a3fce-a81c-4c18-a4b8-b7442b80abdc" />


<img width="1188" height="902" alt="pic3" src="https://github.com/user-attachments/assets/689e90c5-aee7-4ae2-934b-0f411ab963db" />


---

## 👨‍💻 Author

Bogadi Karthik Kumar

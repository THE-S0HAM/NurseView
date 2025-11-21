"""
NurseView - Medical Intelligent Document Processing Pipeline
MIT License - Copyright (c) 2025 Soham Deshmukh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
"""

import json
from datetime import datetime
import google.generativeai as genai
from constants import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

def extract_medical_data(image, document_type):
    """Extract and structure medical data using Gemini Vision"""
    try:
        prompt = f"""Extract all medical information from this {document_type}. Return ONLY valid JSON:
{{
    "patient_info": {{"patient_id": "", "name": "", "dob": "", "gender": ""}},
    "diagnoses": [{{"condition": "", "icd10_code": "", "snomed_code": ""}}],
    "medications": [{{"name": "", "dosage": "", "frequency": "", "rxnorm_code": ""}}],
    "allergies": [{{"allergen": "", "reaction": "", "snomed_code": ""}}],
    "vital_signs": {{"blood_pressure": "", "heart_rate": "", "temperature": ""}},
    "lab_results": [{{"test_name": "", "value": "", "unit": "", "reference_range": ""}}]
}}
Return ONLY JSON, no markdown or extra text."""
        
        response = model.generate_content([prompt, image])
        
        if not response or not response.text:
            return {"error": "No response from Gemini API"}
        
        text = response.text.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        text = text.strip()
        
        result = json.loads(text)
        return result
    except json.JSONDecodeError as e:
        return {"error": f"JSON parsing failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Extraction failed: {str(e)}"}

def convert_to_fhir(data):
    """Convert extracted data to FHIR R4 format"""
    if "error" in data:
        return {"resourceType": "Bundle", "type": "document", "entry": []}
    
    entries = []
    
    if data.get("patient_info"):
        entries.append({
            "resource": {
                "resourceType": "Patient",
                "id": data["patient_info"].get("patient_id", ""),
                "name": [{"text": data["patient_info"].get("name", "")}],
                "birthDate": data["patient_info"].get("dob", ""),
                "gender": data["patient_info"].get("gender", "")
            }
        })
    
    for diagnosis in data.get("diagnoses", []):
        if diagnosis.get("condition"):
            entries.append({
                "resource": {
                    "resourceType": "Condition",
                    "code": {
                        "coding": [{
                            "system": "http://hl7.org/fhir/sid/icd-10",
                            "code": diagnosis.get("icd10_code", ""),
                            "display": diagnosis.get("condition", "")
                        }]
                    }
                }
            })
    
    for medication in data.get("medications", []):
        if medication.get("name"):
            entries.append({
                "resource": {
                    "resourceType": "MedicationStatement",
                    "medicationCodeableConcept": {
                        "coding": [{
                            "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                            "code": medication.get("rxnorm_code", ""),
                            "display": medication.get("name", "")
                        }]
                    },
                    "dosage": [{"text": f"{medication.get('dosage', '')} {medication.get('frequency', '')}"}]
                }
            })
    
    return {"resourceType": "Bundle", "type": "document", "entry": entries}

def convert_to_hl7(data):
    """Convert extracted data to HL7 v2.x format"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    patient = data.get("patient_info", {})
    
    return f"""MSH|^~\\&|NURSEVIEW|HOSPITAL|EMR|HOSPITAL|{timestamp}||ADT^A08|12345|P|2.5
EVN|A08|{timestamp}
PID|1||{patient.get('patient_id', '')}||{patient.get('name', '')}||{patient.get('dob', '')}|{patient.get('gender', '')}
PV1|1|I|ICU^101^1|||||||||||||||V"""

def process_medical_document(image, document_type):
    """Complete NurseView pipeline: Extract, standardize, and convert medical data"""
    medical_data = extract_medical_data(image, document_type)
    fhir_bundle = convert_to_fhir(medical_data)
    hl7_message = convert_to_hl7(medical_data)
    
    return {
        "extracted_data": medical_data,
        "fhir_bundle": fhir_bundle,
        "hl7_message": hl7_message,
        "processing_status": "completed"
    }
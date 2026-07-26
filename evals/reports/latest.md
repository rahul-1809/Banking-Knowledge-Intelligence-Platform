# BKIP RAGAS Evaluation Report

> **Timestamp**: 2026-07-25 11:15:25  
> **Total Benchmark Cases**: 15  
> **Average Latency**: 14454.7 ms  

---

## 📊 Summary Metrics

| Metric | Score | Target Baseline | Status |
|---|---|---|---|
| **Faithfulness** | `0.6933` | `≥ 0.85` | ⚠️ Review |
| **Answer Relevancy** | `0.6333` | `≥ 0.85` | ⚠️ Review |
| **Context Precision** | `0.6867` | `≥ 0.80` | ⚠️ Review |
| **Context Recall** | `0.5733` | `≥ 0.80` | ⚠️ Review |
| **OVERALL SCORE** | **`0.6467`** | `≥ 0.85` | ⚠️ Review |

---

## 📝 Test Case Details

### [eval-001] What are the officially valid documents (OVD) accepted for individual customer identification under RBI KYC norms?
- **Category**: `RBI` | **Latency**: `45873.4 ms`
- **Overall Score**: `1.00` (Faithfulness: `1.00`, Relevancy: `1.00`, Precision: `1.00`, Recall: `1.00`)
- **Ground Truth**: For individual customers, officially valid documents (OVD) include passport, driving licence, Aadhaar (with consent and masking as applicable), and voter identity card.
- **Generated Answer**: According to the RBI Master Direction, the officially valid documents (OVD) accepted for individual customer identification under KYC norms include: 
1. Passport, 
2. Driving licence, 
3. Aadhaar (with consent and masking as applicable), and 
4. Voter identity card. 
[Source: sample_rbi_kyc_circular...
- **Retrieved Sources**: `sample_rbi_kyc_circular.txt, sample_kyc_verification_sop.txt, sample_rbi_kyc_circular.txt, sample_credit_policy.txt, sample_kyc_verification_sop.txt`

---
### [eval-002] What is the periodic KYC updation frequency for low-risk and high-risk banking customers?
- **Category**: `RBI` | **Latency**: `11473.5 ms`
- **Overall Score**: `1.00` (Faithfulness: `1.00`, Relevancy: `1.00`, Precision: `1.00`, Recall: `1.00`)
- **Ground Truth**: KYC records must be updated at least once every ten years for low-risk customers and at least once every eight years for high-risk customers.
- **Generated Answer**: The periodic KYC updation frequency is as follows: 
- Low-risk customers: at least once every 10 years
- High-risk customers: at least once every 8 years
[Source: sample_rbi_kyc_circular.txt, Chunk 1]...
- **Retrieved Sources**: `sample_rbi_kyc_circular.txt, sample_rbi_kyc_circular.txt, sample_kyc_verification_sop.txt, sample_kyc_verification_sop.txt, sample_credit_policy.txt`

---
### [eval-003] What enhanced due diligence (EDD) measures are required for high-risk customers and politically exposed persons?
- **Category**: `RBI` | **Latency**: `11715.0 ms`
- **Overall Score**: `0.90` (Faithfulness: `0.90`, Relevancy: `0.90`, Precision: `0.90`, Recall: `0.90`)
- **Ground Truth**: Enhanced due diligence (EDD) is mandatory for high-risk customers, politically exposed persons (PEPs), and non-face-to-face onboarding. EDD includes obtaining additional information on source of funds and purpose of relationship.
- **Generated Answer**: For high-risk customers and politically exposed persons (PEPs), enhanced due diligence (EDD) measures are mandatory. These measures include obtaining additional information on the source of funds and the purpose of the relationship. [Source: sample_rbi_kyc_circular.txt, Chunk 1] 

Additionally, EDD ...
- **Retrieved Sources**: `sample_rbi_kyc_circular.txt, sample_rbi_kyc_circular.txt, sample_kyc_verification_sop.txt, sample_kyc_verification_sop.txt, sample_credit_policy.txt`

---
### [eval-004] How long must regulated entities maintain KYC documentation and transaction records?
- **Category**: `RBI` | **Latency**: `14418.0 ms`
- **Overall Score**: `0.97` (Faithfulness: `1.00`, Relevancy: `1.00`, Precision: `0.90`, Recall: `1.00`)
- **Ground Truth**: Regulated entities shall maintain KYC documentation and transaction records for at least five years after the business relationship ends or the account is closed, whichever is later.
- **Generated Answer**: Regulated entities (REs) must maintain KYC documentation and transaction records for at least five years after the business relationship ends or the account is closed, whichever is later. [Source: sample_rbi_kyc_circular.txt, Chunk 1]...
- **Retrieved Sources**: `sample_rbi_kyc_circular.txt, sample_rbi_kyc_circular.txt, sample_kyc_verification_sop.txt, sample_kyc_verification_sop.txt, sample_credit_policy.txt`

---
### [eval-005] What are the eligibility criteria for a personal loan including age, income, and credit score?
- **Category**: `SOP` | **Latency**: `2097.7 ms`
- **Overall Score**: `1.00` (Faithfulness: `1.00`, Relevancy: `1.00`, Precision: `1.00`, Recall: `1.00`)
- **Ground Truth**: Applicants must be resident individuals aged 21–60 years with a minimum net monthly income of INR 25,000 and a credit bureau score of 700 or above.
- **Generated Answer**: The eligibility criteria for a personal loan include: 
1. Age: Applicants must be resident individuals aged 21–60 years.
2. Income: A minimum net monthly income of INR 25,000.
3. Credit Score: A credit bureau score of 700 or above, unless approved under exception policy.
[Source: sample_credit_polic...
- **Retrieved Sources**: `sample_credit_policy.txt, sample_credit_policy.txt, sample_rbi_kyc_circular.txt, sample_kyc_verification_sop.txt, sample_rbi_kyc_circular.txt`

---
### [eval-006] What is the maximum debt service coverage ratio (EMI to income limit) for personal loan underwriting?
- **Category**: `SOP` | **Latency**: `11719.5 ms`
- **Overall Score**: `1.00` (Faithfulness: `1.00`, Relevancy: `1.00`, Precision: `1.00`, Recall: `1.00`)
- **Ground Truth**: Total EMI obligations including the proposed loan must not exceed 50% of net monthly income unless compensating factors are documented and approved by the credit committee.
- **Generated Answer**: The maximum debt service coverage ratio for personal loan underwriting is 50% of the net monthly income, unless compensating factors are documented and approved by the credit committee. [Source: sample_credit_policy.txt, Chunk 0]...
- **Retrieved Sources**: `sample_credit_policy.txt, sample_credit_policy.txt, sample_rbi_kyc_circular.txt, sample_rbi_kyc_circular.txt, sample_kyc_verification_sop.txt`

---
### [eval-007] What is the maximum loan amount cap for personal loans relative to monthly income?
- **Category**: `SOP` | **Latency**: `5800.4 ms`
- **Overall Score**: `0.42` (Faithfulness: `0.50`, Relevancy: `0.40`, Precision: `0.50`, Recall: `0.30`)
- **Ground Truth**: The maximum personal loan amount is capped at 24 times net monthly income or INR 25,00,000, whichever is lower.
- **Generated Answer**: ...
- **Retrieved Sources**: `None`

---
### [eval-008] Who has approval authority for personal loans above INR 5,00,000?
- **Category**: `SOP` | **Latency**: `11778.7 ms`
- **Overall Score**: `0.42` (Faithfulness: `0.50`, Relevancy: `0.40`, Precision: `0.50`, Recall: `0.30`)
- **Ground Truth**: Loans up to INR 5,00,000 may be approved by the branch credit officer. Amounts above INR 5,00,000 require regional credit head approval, while exceptions require committee review.
- **Generated Answer**: ...
- **Retrieved Sources**: `None`

---
### [eval-009] What activities are prohibited regarding the use of personal loan proceeds?
- **Category**: `SOP` | **Latency**: `7315.8 ms`
- **Overall Score**: `0.42` (Faithfulness: `0.50`, Relevancy: `0.40`, Precision: `0.50`, Recall: `0.30`)
- **Ground Truth**: Loan proceeds must not be used for speculative trading, cryptocurrency investment, or any activity prohibited under internal AML policy.
- **Generated Answer**: ...
- **Retrieved Sources**: `None`

---
### [eval-0010] What is the internal SOP procedure for handling Aadhaar details during customer verification?
- **Category**: `SOP` | **Latency**: `14022.7 ms`
- **Overall Score**: `0.42` (Faithfulness: `0.50`, Relevancy: `0.40`, Precision: `0.50`, Recall: `0.30`)
- **Ground Truth**: Branch staff must capture customer consent for Aadhaar-based verification where used, and staff must not store full Aadhaar numbers in operational notes.
- **Generated Answer**: ...
- **Retrieved Sources**: `None`

---
### [eval-0011] What is the internal escalation timeframe and process when suspected forged documents or PEP indicators are identified?
- **Category**: `SOP` | **Latency**: `4108.2 ms`
- **Overall Score**: `0.42` (Faithfulness: `0.50`, Relevancy: `0.40`, Precision: `0.50`, Recall: `0.30`)
- **Ground Truth**: Any mismatch in identity details, suspected forged documents, or PEP indicators must be escalated to the branch compliance officer within 24 hours.
- **Generated Answer**: ...
- **Retrieved Sources**: `None`

---
### [eval-0012] What mandatory financial documents are required to apply for a personal loan?
- **Category**: `SOP` | **Latency**: `9733.2 ms`
- **Overall Score**: `0.42` (Faithfulness: `0.50`, Relevancy: `0.40`, Precision: `0.50`, Recall: `0.30`)
- **Ground Truth**: Mandatory documents include identity proof, address proof, income proof (salary slips or ITR), and bank statements for the last six months.
- **Generated Answer**: ...
- **Retrieved Sources**: `None`

---
### [eval-0013] Who must approve high-risk customer profiles before account activation according to the internal SOP?
- **Category**: `SOP` | **Latency**: `10883.0 ms`
- **Overall Score**: `0.42` (Faithfulness: `0.50`, Relevancy: `0.40`, Precision: `0.50`, Recall: `0.30`)
- **Ground Truth**: High-risk profiles must be routed to the compliance officer for EDD approval before account activation.
- **Generated Answer**: ...
- **Retrieved Sources**: `None`

---
### [eval-0014] What is the core objective of the RBI KYC framework for regulated entities?
- **Category**: `RBI` | **Latency**: `41760.5 ms`
- **Overall Score**: `0.42` (Faithfulness: `0.50`, Relevancy: `0.40`, Precision: `0.50`, Recall: `0.30`)
- **Ground Truth**: Regulated entities shall establish a robust KYC framework to prevent banks from being used for money laundering or terrorist financing activities.
- **Generated Answer**: ...
- **Retrieved Sources**: `None`

---
### [eval-0015] How long must branch staff maintain the verification checklist and audit trail for retail customer onboarding?
- **Category**: `SOP` | **Latency**: `14121.0 ms`
- **Overall Score**: `0.42` (Faithfulness: `0.50`, Relevancy: `0.40`, Precision: `0.50`, Recall: `0.30`)
- **Ground Truth**: Branch staff must maintain the verification checklist and audit trail for a minimum of five years.
- **Generated Answer**: ...
- **Retrieved Sources**: `None`

---

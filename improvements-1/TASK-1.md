# TASK-1: Refine Terminology in the Paper

## 1. Replace "High Watermark (LSO)" with a more precise definition

The current phrasing in the paper is imprecise and could be misleading. The LSO is the key concept for `read_committed` consumers, and it's important to be clear about this.

**Action:** Revise the paper to explicitly differentiate between the High Watermark (HW) and the Last Stable Offset (LSO). State that the validator consumer's progress should be measured against the LSO, and update any relevant diagrams or explanations to reflect this.

## 2. Rename "Transactional Watermarks"

The term "watermark" is already heavily used in Kafka, and overloading it could cause confusion.

**Action:** Rename "Transactional Watermarks" to something more descriptive, such as **"Business Transaction Timestamps"** or **"Transaction Lifecycle Timestamps."** Add a clarification that these are based on the timestamps of the business events themselves, not on Kafka's internal offset watermarks.

### 1. LSO vs. High Watermark

You are absolutely correct. The current phrasing is imprecise and could be misleading. The LSO is the key concept for `read_committed` consumers, and it's important to be clear about this.

*   **Plan:** I will revise the paper to explicitly differentiate between the High Watermark (HW) and the Last Stable Offset (LSO). I will state that the validator consumer's progress should be measured against the LSO, and I will update any relevant diagrams or explanations to reflect this.
export type Course = {
  id: number
  user_id: string
  name: string
  created_at: string
}

export type DocumentItem = {
  id: number
  user_id: string
  course_id: number | null
  filename: string
  file_type: string
  status: string
  created_at: string
  chunk_count: number
}

export type ChatSource = {
  chunk_id: number
  document_id: number
  course_id: number | null
  filename: string
  content: string
  metadata: Record<string, unknown>
  distance: number
  similarity: number
}

export type ChatClaim = {
  claim: string
  source_chunk_ids: number[]
  support_level:
    | 'fully_supported'
    | 'partially_supported'
    | 'unsupported'
    | 'contradicted'
    | 'not_enough_information'
  evidence_quote: string
}

export type AnswerStatus =
  | 'answered'
  | 'partially_answered'
  | 'refused_no_evidence'
  | 'refused_ambiguous_material'
  | 'needs_more_material'

export type EvidenceStrength = 'none' | 'low' | 'medium' | 'high' | 'conflicting'
export type TutorEvidenceStrength =
  | 'high'
  | 'medium'
  | 'low'
  | 'insufficient'
  | 'not_required'

export type ChatResponse = {
  query: string
  user_id: string
  course_id: number | null
  mode: string
  answer_status: AnswerStatus
  answer: string
  claims: ChatClaim[]
  overall_groundedness: number
  evidence_state: {
    evidence_strength: EvidenceStrength
    source_coverage: number
    supported_claim_count: number
    unsupported_claim_count: number
    contradicted_claim_count: number
    answer_status: AnswerStatus
  }
  sources: ChatSource[]
}

export type ChatCompareResponse = {
  query: string
  user_id: string
  course_id: number | null
  grounded: ChatResponse
  ungrounded: ChatResponse
}

export type QuizOption = {
  id: string
  text: string
}

export type QuizItem = {
  id: number
  user_id: string
  course_id: number | null
  question: string
  answer: string
  difficulty: string
  source_chunk_ids: number[]
  evidence_quote: string
  options: QuizOption[]
  explanation: string
  question_type: string
  traceability_label: string
  created_at: string
  archived_at: string | null
}

export type QuizGenerateResponse = {
  topic: string
  user_id: string
  course_id: number | null
  items: QuizItem[]
}

export type QuizAttemptResponse = {
  id: number
  user_id: string
  course_id: number | null
  quiz_item_id: number
  selected_option_id: string
  selected_option_text: string
  correct_option_id: string
  correct_option_text: string
  is_correct: boolean
  explanation: string
  source_chunk_ids: number[]
  attempted_at: string
}

export type QuizItemRemovalResponse = {
  item_id: number
  action: 'deleted' | 'archived'
  archived_at: string | null
}

export type ReviewRecord = {
  id: number
  user_id: string
  item_id: number
  course_id: number | null
  rating: number
  is_correct: boolean
  reviewed_at: string
  stability: number
  difficulty: number
  due_at: string
}

export type DueReviewItem = {
  item: QuizItem
  latest_review: ReviewRecord | null
}

export type MasteryResponse = {
  user_id: string
  course_id: number | null
  summary: {
    total_items: number
    reviewed_items: number
    due_items: number
    average_mastery: number
  }
  items: Array<{
    item_id: number
    question: string
    difficulty: string
    mastery_probability: number
    review_count: number
    latest_rating: number | null
    latest_is_correct: boolean | null
    due_at: string | null
    is_due: boolean
  }>
}

export type LearnerState = {
  user_id: string
  course_id: number | null
  mastery_score: number
  recent_accuracy: number
  attempt_count: number
  consecutive_errors: number
  last_reviewed_at: string | null
  review_due: boolean
}

export type TutorDecision = {
  decision_id: number
  user_id: string
  course_id: number | null
  query: string
  detected_intent: 'explain' | 'hint' | 'practice' | 'review' | 'unknown'
  selected_action: 'explain' | 'hint' | 'quiz' | 'review' | 'refuse'
  response_strategy:
    | 'scaffolded'
    | 'guided'
    | 'concise'
    | 'challenging'
    | 'refusal'
    | 'review_drill'
  primary_reason: string
  teaching_reason: string
  suggested_next_step: string
  policy_version: string
  learner_state_snapshot: LearnerState
  evidence_state_snapshot: {
    evidence_strength: TutorEvidenceStrength
    source_coverage: number
    retrieved_chunk_count: number
    top_similarity: number
    requires_evidence: boolean
    reason: string
  }
}

export type TutorResponse = {
  decision: TutorDecision
  answer_status:
    | 'answered'
    | 'partially_answered'
    | 'refused_no_evidence'
    | 'refused_ambiguous_material'
    | 'needs_more_material'
    | 'review_ready'
    | 'quiz_ready'
  answer: string
  claims: ChatClaim[]
  sources: ChatSource[]
  quiz_items: QuizItem[]
  review_items: DueReviewItem[]
  suggested_next_step: string
}

export type TutorOutcomeResponse = {
  decision_id: number
  outcome: Record<string, unknown>
}

export type AnswerEvaluation = {
  user_id: string
  course_id: number | null
  claim_count: number
  supported_claim_count: number
  unsupported_claim_count: number
  contradicted_claim_count: number
  citation_precision: number
  unsupported_claim_rate: number
  groundedness_score: number
  correct_refusal: boolean
}

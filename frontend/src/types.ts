export type DocumentItem = {
  id: number
  user_id: string
  filename: string
  file_type: string
  status: string
  created_at: string
  chunk_count: number
}

export type ChatSource = {
  chunk_id: number
  document_id: number
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

export type ChatResponse = {
  query: string
  user_id: string
  mode: string
  answer_status:
    | 'answered'
    | 'partially_answered'
    | 'refused_no_evidence'
    | 'refused_ambiguous_material'
    | 'needs_more_material'
  answer: string
  claims: ChatClaim[]
  overall_groundedness: number
  sources: ChatSource[]
}

export type ChatCompareResponse = {
  query: string
  user_id: string
  grounded: ChatResponse
  ungrounded: ChatResponse
}

export type QuizItem = {
  id: number
  user_id: string
  question: string
  answer: string
  difficulty: string
  source_chunk_ids: number[]
  evidence_quote: string
  question_type: string
  traceability_label: string
  created_at: string
}

export type QuizGenerateResponse = {
  topic: string
  user_id: string
  items: QuizItem[]
}

export type ReviewRecord = {
  id: number
  user_id: string
  item_id: number
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

export type AnswerEvaluation = {
  claim_count: number
  supported_claim_count: number
  unsupported_claim_count: number
  contradicted_claim_count: number
  citation_precision: number
  unsupported_claim_rate: number
  groundedness_score: number
  correct_refusal: boolean
}

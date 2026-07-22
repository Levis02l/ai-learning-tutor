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

export type Answerability =
  | 'answerable'
  | 'partially_answerable'
  | 'unanswerable'

export type QuizOption = {
  id: string
  text: string
}

export type QuizItem = {
  id: number
  user_id: string
  course_id: number | null
  concept_id: number | null
  question: string
  answer: string
  difficulty: string
  origin:
    | 'manual_practice'
    | 'policy_quiz'
    | 'comprehension_check'
    | 'socratic_completion_check'
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

export type ProgressConceptStatus =
  | 'unobserved'
  | 'needs_attention'
  | 'developing'
  | 'strong'

export type ProgressMisconception = {
  id: number
  misconception_type: string
  description: string
  confidence: number
  quiz_attempt_id: number
  created_at: string | null
}

export type ProgressPrerequisite = {
  id: number
  name: string
  confidence: number
}

export type ProgressSocraticActivity = {
  completed_sessions: number
  completion_attempts: number
  latest_session_id: number | null
  latest_completed_at: string | null
  latest_completion_quiz_item_id: number | null
  latest_completion_quiz_attempt_id: number | null
  latest_completion_correct: boolean | null
}

export type ProgressConcept = {
  concept_id: number
  concept_name: string
  state_status: 'observed' | 'unobserved'
  status: ProgressConceptStatus
  mastery_score: number | null
  recent_accuracy: number | null
  attempt_count: number
  consecutive_errors: number
  last_attempted_at: string | null
  review_due: boolean
  needs_attention: boolean
  attention_reasons: string[]
  latest_misconception: ProgressMisconception | null
  prerequisites: ProgressPrerequisite[]
  socratic_activity: ProgressSocraticActivity
}

export type CourseProgress = {
  user_id: string
  course_id: number
  summary: {
    total_concepts: number
    observed_concepts: number
    unobserved_concepts: number
    needs_attention_count: number
    review_due_count: number
    strong_count: number
    developing_count: number
    socratic_completed_count: number
    socratic_completion_attempt_count: number
  }
  concepts: ProgressConcept[]
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
    | 'contrastive'
    | 'definition_clarification'
    | 'prerequisite_scaffolded'
    | 'reasoning_guidance'
    | 'source_correction'
  primary_reason: string
  teaching_reason: string
  suggested_next_step: string
  policy_version: string
  learner_state_scope: 'course' | 'concept'
  learner_state_snapshot: LearnerState
  concept_state_snapshot: {
    concept_id: number
    concept_name: string
    state_status: 'observed' | 'unobserved'
    mastery_score: number | null
    recent_accuracy: number | null
    attempt_count: number
    consecutive_errors: number
    last_attempted_at: string | null
    review_due: boolean
    needs_attention: boolean
  } | null
  misconception_snapshot: {
    id: number
    misconception_type: string
    description: string
    confidence: number
    quiz_attempt_id: number
    concept_id: number
    created_at: string | null
  } | null
  evidence_state_snapshot: {
    evidence_strength: TutorEvidenceStrength
    source_coverage: number
    retrieved_chunk_count: number
    top_similarity: number
    requires_evidence: boolean
    reason: string
    retrieval_scope: 'course' | 'concept' | 'concept_with_course_fallback' | 'not_required'
    source_chunk_ids: number[]
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

export type SocraticStatus = 'active' | 'completed' | 'abandoned'

export type SocraticStage =
  | 'diagnostic'
  | 'hint_1'
  | 'hint_2'
  | 'final_explanation'
  | 'grounded_summary'

export type SocraticAssessment =
  | 'correct'
  | 'partially_correct'
  | 'incorrect'
  | 'off_topic'

export type SocraticTurn = {
  id: number
  session_id: number
  turn_number: number
  stage: SocraticStage
  tutor_message: string
  student_response: string | null
  assessment: SocraticAssessment | null
  assessment_reason: string | null
  created_at: string
}

export type SocraticSession = {
  id: number
  user_id: string
  course_id: number | null
  concept_id: number | null
  source_policy_decision_id: number | null
  completion_quiz_item_id: number | null
  completion_quiz_attempt_id: number | null
  query: string
  status: SocraticStatus
  current_stage: SocraticStage
  turn_count: number
  max_turns: number
  message: string
  assessment: SocraticAssessment | null
  assessment_reason: string | null
  learner_state_snapshot: LearnerState
  concept_snapshot: TutorDecision['concept_state_snapshot']
  misconception_snapshot: TutorDecision['misconception_snapshot']
  evidence_state_snapshot: TutorDecision['evidence_state_snapshot']
  evidence_chunks_snapshot: ChatSource[]
  turns: SocraticTurn[]
  created_at: string
  completed_at: string | null
}

export type SocraticCompletionCheckResponse = {
  session: SocraticSession
  item: QuizItem
}

export type SocraticCompletionAttemptResponse = {
  session: SocraticSession
  attempt: QuizAttemptResponse
}

export type AnswerEvaluation = {
  user_id: string
  course_id: number | null
  answerability: Answerability
  claim_count: number
  supported_claim_count: number
  unsupported_claim_count: number
  contradicted_claim_count: number
  cited_claim_count: number
  citation_applicable: boolean
  automatic_cited_claim_support_rate: number | null
  generated_unsupported_claim_rate: number
  generation_groundedness_score: number
  automatic_refusal_correctness: boolean | null
  // Deprecated compatibility fields retained by the API for older views.
  citation_precision: number | null
  citation_coverage: number | null
  unsupported_claim_rate: number
  groundedness_score: number
  refused_by_status: boolean
  semantic_refusal: boolean
  effective_refusal: boolean
  correct_refusal: boolean | null
}

import type {
  AnswerEvaluation,
  ChatCompareResponse,
  ChatResponse,
  DocumentItem,
  DueReviewItem,
  MasteryResponse,
  QuizGenerateResponse,
  QuizItem,
  ReviewRecord,
} from './types'

const API_BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    const message =
      payload && typeof payload.detail === 'string'
        ? payload.detail
        : `Request failed with ${response.status}`
    throw new Error(message)
  }

  return payload as T
}

export async function getHealth(): Promise<{ status: string }> {
  return request('/health/live')
}

export async function listDocuments(userId: string): Promise<DocumentItem[]> {
  return request(`/documents?user_id=${encodeURIComponent(userId)}`)
}

export async function uploadDocument(
  userId: string,
  file: File,
): Promise<DocumentItem> {
  const formData = new FormData()
  formData.append('user_id', userId)
  formData.append('file', file)

  return request('/documents', {
    method: 'POST',
    body: formData,
  })
}

export async function chat(
  userId: string,
  query: string,
  topK: number,
): Promise<ChatResponse> {
  return request('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, query, top_k: topK }),
  })
}

export async function compareChat(
  userId: string,
  query: string,
  topK: number,
): Promise<ChatCompareResponse> {
  return request('/chat/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, query, top_k: topK }),
  })
}

export async function generateQuiz(
  userId: string,
  topic: string,
  count: number,
  difficulty: string,
  topK: number,
): Promise<QuizGenerateResponse> {
  return request('/quiz/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      topic,
      count,
      difficulty,
      top_k: topK,
    }),
  })
}

export async function listQuizItems(userId: string): Promise<QuizItem[]> {
  return request(`/quiz/items?user_id=${encodeURIComponent(userId)}&limit=50`)
}

export async function listDueReviews(userId: string): Promise<DueReviewItem[]> {
  return request(`/reviews/due?user_id=${encodeURIComponent(userId)}&limit=20`)
}

export async function submitReview(
  userId: string,
  itemId: number,
  rating: number,
  isCorrect: boolean,
): Promise<ReviewRecord> {
  return request('/reviews', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      item_id: itemId,
      rating,
      is_correct: isCorrect,
    }),
  })
}

export async function getMastery(userId: string): Promise<MasteryResponse> {
  return request(`/mastery?user_id=${encodeURIComponent(userId)}`)
}

export async function evaluateAnswer(
  response: ChatResponse,
  expectedAnswerable: boolean,
): Promise<AnswerEvaluation> {
  return request('/evaluation/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      expected_answerable: expectedAnswerable,
      response,
    }),
  })
}

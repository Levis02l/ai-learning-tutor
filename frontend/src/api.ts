import type {
  AnswerEvaluation,
  ChatCompareResponse,
  ChatResponse,
  Course,
  DocumentItem,
  DueReviewItem,
  LearnerState,
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

function scopedQuery(userId: string, courseId?: number | null, extra = '') {
  const params = new URLSearchParams({ user_id: userId })
  if (courseId != null) params.set('course_id', String(courseId))
  if (extra) {
    for (const [key, value] of new URLSearchParams(extra)) {
      params.set(key, value)
    }
  }
  return params.toString()
}

function scopedBody(userId: string, courseId?: number | null) {
  return courseId == null ? { user_id: userId } : { user_id: userId, course_id: courseId }
}

export async function getHealth(): Promise<{ status: string }> {
  return request('/health/live')
}

export async function listCourses(userId: string): Promise<Course[]> {
  return request(`/courses?user_id=${encodeURIComponent(userId)}`)
}

export async function createCourse(userId: string, name: string): Promise<Course> {
  return request('/courses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, name }),
  })
}

export async function deleteCourse(userId: string, courseId: number): Promise<void> {
  await request<void>(`/courses/${courseId}?user_id=${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  })
}

export async function listDocuments(
  userId: string,
  courseId?: number | null,
): Promise<DocumentItem[]> {
  return request(`/documents?${scopedQuery(userId, courseId)}`)
}

export async function uploadDocument(
  userId: string,
  file: File,
  courseId?: number | null,
): Promise<DocumentItem> {
  const formData = new FormData()
  formData.append('user_id', userId)
  if (courseId != null) formData.append('course_id', String(courseId))
  formData.append('file', file)

  return request('/documents', {
    method: 'POST',
    body: formData,
  })
}

export async function deleteDocument(
  userId: string,
  documentId: number,
): Promise<void> {
  await request<void>(
    `/documents/${documentId}?user_id=${encodeURIComponent(userId)}`,
    {
      method: 'DELETE',
    },
  )
}

export async function chat(
  userId: string,
  query: string,
  topK: number,
  courseId?: number | null,
): Promise<ChatResponse> {
  return request('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...scopedBody(userId, courseId), query, top_k: topK }),
  })
}

export async function compareChat(
  userId: string,
  query: string,
  topK: number,
  courseId?: number | null,
): Promise<ChatCompareResponse> {
  return request('/chat/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...scopedBody(userId, courseId), query, top_k: topK }),
  })
}

export async function generateQuiz(
  userId: string,
  topic: string,
  count: number,
  difficulty: string,
  topK: number,
  courseId?: number | null,
): Promise<QuizGenerateResponse> {
  return request('/quiz/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...scopedBody(userId, courseId),
      topic,
      count,
      difficulty,
      top_k: topK,
    }),
  })
}

export async function listQuizItems(
  userId: string,
  courseId?: number | null,
): Promise<QuizItem[]> {
  return request(`/quiz/items?${scopedQuery(userId, courseId, 'limit=50')}`)
}

export async function listDueReviews(
  userId: string,
  courseId?: number | null,
): Promise<DueReviewItem[]> {
  return request(`/reviews/due?${scopedQuery(userId, courseId, 'limit=20')}`)
}

export async function submitReview(
  userId: string,
  itemId: number,
  rating: number,
  isCorrect: boolean,
  courseId?: number | null,
): Promise<ReviewRecord> {
  return request('/reviews', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...scopedBody(userId, courseId),
      item_id: itemId,
      rating,
      is_correct: isCorrect,
    }),
  })
}

export async function getMastery(
  userId: string,
  courseId?: number | null,
): Promise<MasteryResponse> {
  return request(`/mastery?${scopedQuery(userId, courseId)}`)
}

export async function getLearnerState(
  userId: string,
  courseId?: number | null,
): Promise<LearnerState> {
  return request(`/learner-state?${scopedQuery(userId, courseId)}`)
}

export async function evaluateAnswer(
  response: ChatResponse,
  expectedAnswerable: boolean,
  userId: string,
  courseId?: number | null,
): Promise<AnswerEvaluation> {
  return request('/evaluation/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...scopedBody(userId, courseId),
      expected_answerable: expectedAnswerable,
      response,
    }),
  })
}

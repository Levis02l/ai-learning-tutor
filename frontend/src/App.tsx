import {
  BarChart3,
  Bot,
  BookOpen,
  Brain,
  CheckCircle2,
  ClipboardList,
  FileText,
  FileUp,
  FolderPlus,
  Gauge,
  Library,
  Loader2,
  MessagesSquare,
  MessageSquareText,
  RefreshCw,
  SearchCheck,
  Send,
  Trash2,
  Upload,
} from 'lucide-react'
import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react'

import {
  chat,
  compareChat,
  createCourse,
  createSocraticCompletionCheck,
  deleteCourse,
  deleteDocument,
  deleteQuizItem,
  evaluateAnswer,
  generateQuiz,
  getCourseProgress,
  getHealth,
  getLearnerState,
  getMastery,
  getSocraticSession,
  linkTutorOutcome,
  listCourses,
  listDocuments,
  listDueReviews,
  listQuizItems,
  respondToSocraticSession,
  startSocraticSession,
  submitSocraticCompletionAttempt,
  submitQuizAttempt,
  submitReview,
  tutorRespond,
  uploadDocument,
} from './api'
import type {
  AnswerEvaluation,
  ChatCompareResponse,
  ChatResponse,
  Course,
  CourseProgress,
  DocumentItem,
  DueReviewItem,
  LearnerState,
  MasteryResponse,
  QuizAttemptResponse,
  QuizItem,
  ProgressConceptStatus,
  SocraticSession,
  TutorResponse,
} from './types'

type View =
  | 'documents'
  | 'tutor'
  | 'chat'
  | 'quiz'
  | 'review'
  | 'progress'
  | 'evaluation'
type HealthStatus = 'checking' | 'connected' | 'unreachable'

const userIdDefault = 'demo-user'

function App() {
  const [activeView, setActiveView] = useState<View>('documents')
  const [userId, setUserId] = useState(userIdDefault)
  const [health, setHealth] = useState<HealthStatus>('checking')
  const [courses, setCourses] = useState<Course[]>([])
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null)
  const [newCourseName, setNewCourseName] = useState('')
  const [courseBusy, setCourseBusy] = useState(false)
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [quizItems, setQuizItems] = useState<QuizItem[]>([])
  const [dueReviews, setDueReviews] = useState<DueReviewItem[]>([])
  const [mastery, setMastery] = useState<MasteryResponse | null>(null)
  const [learnerState, setLearnerState] = useState<LearnerState | null>(null)
  const [globalError, setGlobalError] = useState('')

  const selectedCourse = useMemo(
    () => courses.find((course) => course.id === selectedCourseId) ?? null,
    [courses, selectedCourseId],
  )
  const scopedCourseId = selectedCourseId ?? undefined

  const refreshHealth = useCallback(async () => {
    try {
      const response = await getHealth()
      setHealth(response.status === 'ok' ? 'connected' : 'unreachable')
    } catch {
      setHealth('unreachable')
    }
  }, [])

  const refreshCoreData = useCallback(async () => {
    setGlobalError('')
    try {
      const [courseList, docs, quizzes, due, masterySnapshot, state] = await Promise.all([
        listCourses(userId),
        listDocuments(userId, scopedCourseId),
        listQuizItems(userId, scopedCourseId),
        listDueReviews(userId, scopedCourseId),
        getMastery(userId, scopedCourseId),
        getLearnerState(userId, scopedCourseId),
      ])
      setCourses(courseList)
      if (
        selectedCourseId !== null &&
        !courseList.some((course) => course.id === selectedCourseId)
      ) {
        setSelectedCourseId(null)
      }
      setDocuments(docs)
      setQuizItems(quizzes)
      setDueReviews(due)
      setMastery(masterySnapshot)
      setLearnerState(state)
    } catch (error) {
      setGlobalError(getErrorMessage(error))
    }
  }, [scopedCourseId, selectedCourseId, userId])

  async function handleCreateCourse(event: FormEvent) {
    event.preventDefault()
    const name = newCourseName.trim()
    if (!name) return

    setCourseBusy(true)
    setGlobalError('')
    try {
      const course = await createCourse(userId, name)
      setCourses((current) => [course, ...current])
      setSelectedCourseId(course.id)
      setNewCourseName('')
    } catch (error) {
      setGlobalError(getErrorMessage(error))
    } finally {
      setCourseBusy(false)
    }
  }

  async function handleDeleteSelectedCourse() {
    if (!selectedCourse) return
    const confirmed = window.confirm(
      `Delete course "${selectedCourse.name}" and all its materials?`,
    )
    if (!confirmed) return

    setCourseBusy(true)
    setGlobalError('')
    try {
      await deleteCourse(userId, selectedCourse.id)
      setCourses((current) =>
        current.filter((course) => course.id !== selectedCourse.id),
      )
      setSelectedCourseId(null)
    } catch (error) {
      setGlobalError(getErrorMessage(error))
    } finally {
      setCourseBusy(false)
    }
  }

  useEffect(() => {
    void refreshHealth()
  }, [refreshHealth])

  useEffect(() => {
    void refreshCoreData()
  }, [refreshCoreData])

  const navItems = [
    { id: 'documents' as const, label: 'Documents', icon: Library },
    { id: 'tutor' as const, label: 'Adaptive Tutor', icon: Bot },
    { id: 'chat' as const, label: 'Evidence Chat', icon: MessageSquareText },
    { id: 'quiz' as const, label: 'Quiz Lab', icon: ClipboardList },
    { id: 'review' as const, label: 'Review', icon: Brain },
    { id: 'progress' as const, label: 'Progress', icon: BarChart3 },
    { id: 'evaluation' as const, label: 'Evaluation', icon: SearchCheck },
  ]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <BookOpen size={22} aria-hidden="true" />
          </div>
          <div>
            <h1 className="brand-title">AI 学习导师</h1>
            <p className="brand-subtitle">Evidence-aware tutor</p>
          </div>
        </div>

        <label className="user-block">
          <span className="field-label">User ID</span>
          <input
            className="input"
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
          />
        </label>

        <section className="course-block" aria-label="Course workspace">
          <div className="course-block-header">
            <span className="field-label">Course Workspace</span>
            <span className="badge info">{courses.length}</span>
          </div>
          <select
            className="select"
            value={selectedCourseId ?? 'all'}
            onChange={(event) => {
              const value = event.target.value
              setSelectedCourseId(value === 'all' ? null : Number(value))
            }}
          >
            <option value="all">All materials</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.name}
              </option>
            ))}
          </select>
          <form className="course-create" onSubmit={handleCreateCourse}>
            <input
              className="input"
              maxLength={120}
              onChange={(event) => setNewCourseName(event.target.value)}
              placeholder="New course name"
              value={newCourseName}
            />
            <button
              aria-label="Create course"
              className="icon-button"
              disabled={courseBusy || !newCourseName.trim()}
              title="Create course"
              type="submit"
            >
              {courseBusy ? (
                <Loader2 className="spin" size={16} aria-hidden="true" />
              ) : (
                <FolderPlus size={16} aria-hidden="true" />
              )}
            </button>
          </form>
          {selectedCourse && (
            <button
              className="button ghost full"
              disabled={courseBusy}
              onClick={() => void handleDeleteSelectedCourse()}
              type="button"
            >
              <Trash2 size={15} aria-hidden="true" />
              Delete course
            </button>
          )}
        </section>

        <nav className="nav" aria-label="Primary navigation">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <button
                className={`nav-button ${activeView === item.id ? 'active' : ''}`}
                key={item.id}
                onClick={() => setActiveView(item.id)}
                type="button"
              >
                <Icon size={18} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div className="sidebar-footer">
          <span className={statusDotClass(health)} />
          <span>{healthLabel(health)}</span>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h2 className="page-title">{pageTitle(activeView)}</h2>
            <p className="page-kicker">{pageKicker(activeView)}</p>
          </div>
          <div className="toolbar">
            <span className="scope-pill">
              {selectedCourse ? selectedCourse.name : 'All materials'}
            </span>
            <button className="button secondary" onClick={refreshCoreData} type="button">
              <RefreshCw size={16} aria-hidden="true" />
              Refresh
            </button>
          </div>
        </header>

        {globalError && <div className="error">{globalError}</div>}

        {activeView === 'documents' && (
          <DocumentsView
            courseId={selectedCourseId}
            courseName={selectedCourse?.name ?? null}
            documents={documents}
            userId={userId}
            onUploaded={refreshCoreData}
          />
        )}
        {activeView === 'tutor' && (
          <TutorView
            courseId={selectedCourseId}
            userId={userId}
            onResponded={refreshCoreData}
          />
        )}
        {activeView === 'chat' && <ChatView courseId={selectedCourseId} userId={userId} />}
        {activeView === 'quiz' && (
          <QuizView
            courseId={selectedCourseId}
            items={quizItems}
            materialCount={documents.length}
            userId={userId}
            onGenerated={refreshCoreData}
          />
        )}
        {activeView === 'review' && (
          <ReviewView
            courseId={selectedCourseId}
            dueReviews={dueReviews}
            learnerState={learnerState}
            mastery={mastery}
            userId={userId}
            onReviewed={refreshCoreData}
          />
        )}
        {activeView === 'progress' && (
          <ProgressView
            courseId={selectedCourseId}
            courseName={selectedCourse?.name ?? null}
            userId={userId}
          />
        )}
        {activeView === 'evaluation' && <EvaluationView courseId={selectedCourseId} userId={userId} />}
      </main>
    </div>
  )
}

function TutorView({
  courseId,
  userId,
  onResponded,
}: {
  courseId: number | null
  userId: string
  onResponded: () => Promise<void>
}) {
  const [query, setQuery] = useState('Explain artificial intelligence')
  const [topK, setTopK] = useState(5)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [response, setResponse] = useState<TutorResponse | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!query.trim()) return

    setBusy(true)
    setError('')
    setResponse(null)
    try {
      const result = await tutorRespond(userId, query, topK, courseId)
      setResponse(result)
      await onResponded()
    } catch (tutorError) {
      setError(getErrorMessage(tutorError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid two">
      <section className="panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <Bot size={18} aria-hidden="true" />
            Tutor
          </h3>
          <span className="badge info">policy-aware</span>
        </div>
        <div className="panel-body stack">
          <form className="stack" onSubmit={handleSubmit}>
            <textarea
              className="textarea"
              onChange={(event) => setQuery(event.target.value)}
              value={query}
            />
            <div className="form-row">
              <label>
                <span className="field-label">Top K</span>
                <input
                  className="input"
                  max={10}
                  min={1}
                  onChange={(event) => setTopK(Number(event.target.value))}
                  type="number"
                  value={topK}
                />
              </label>
              <div />
              <button className="button" disabled={busy || !query.trim()} type="submit">
                {busy ? (
                  <Loader2 className="spin" size={16} aria-hidden="true" />
                ) : (
                  <Send size={16} aria-hidden="true" />
                )}
                Respond
              </button>
            </div>
          </form>

          {error && <div className="error">{error}</div>}

          {!response ? (
            <>
              <EmptyState label="Ask the tutor to trigger policy-aware teaching." />
              <TutorSocraticSection
                courseId={courseId}
                onOutcomeRecorded={onResponded}
                response={null}
                topK={topK}
                userId={userId}
              />
            </>
          ) : (
            <>
              <TutorAnswerCard response={response} />
              <TutorSocraticSection
                courseId={courseId}
                onOutcomeRecorded={onResponded}
                response={response}
                topK={topK}
                userId={userId}
              />
              {response.quiz_items.length > 0 && (
                <TutorQuizItems
                  courseId={courseId}
                  decisionId={response.decision.decision_id}
                  items={response.quiz_items}
                  onOutcomeLinked={onResponded}
                  userId={userId}
                />
              )}
              {response.review_items.length > 0 && (
                <TutorReviewItems
                  courseId={courseId}
                  decisionId={response.decision.decision_id}
                  items={response.review_items}
                  onOutcomeLinked={onResponded}
                  userId={userId}
                />
              )}
              {response.claims.length > 0 && <TutorClaims response={response} />}
            </>
          )}
        </div>
      </section>

      <TutorDecisionPanel response={response} />
    </div>
  )
}

function TutorAnswerCard({ response }: { response: TutorResponse }) {
  return (
    <div className="answer-card">
      <div className="panel-header">
        <h3 className="panel-title">
          <MessageSquareText size={18} aria-hidden="true" />
          Response
        </h3>
        <span className={`badge ${tutorStatusBadgeClass(response.answer_status)}`}>
          {response.answer_status}
        </span>
      </div>
      <div className="panel-body stack">
        <div className="badge-row">
          <span className="badge info">{response.decision.selected_action}</span>
          <span className="badge">{response.decision.response_strategy}</span>
          <span className="badge">{response.decision.detected_intent}</span>
        </div>
        <p className="answer">{response.answer}</p>
        <div className="notice">{response.suggested_next_step}</div>
      </div>
    </div>
  )
}

function TutorSocraticSection({
  courseId,
  onOutcomeRecorded,
  response,
  topK,
  userId,
}: {
  courseId: number | null
  onOutcomeRecorded: () => Promise<void>
  response: TutorResponse | null
  topK: number
  userId: string
}) {
  const [session, setSession] = useState<SocraticSession | null>(null)
  const [completionItem, setCompletionItem] = useState<QuizItem | null>(null)
  const [completionFeedback, setCompletionFeedback] =
    useState<QuizAttemptResponse | null>(null)
  const [selectedCompletionOption, setSelectedCompletionOption] = useState('')
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [completionBusy, setCompletionBusy] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [error, setError] = useState('')

  const decisionId = response?.decision.decision_id ?? null
  const latestStorageKey = useMemo(
    () => socraticLatestStorageKey(userId, courseId),
    [courseId, userId],
  )
  const decisionStorageKey = useMemo(
    () =>
      decisionId == null
        ? null
        : socraticDecisionStorageKey(userId, courseId, decisionId),
    [courseId, decisionId, userId],
  )

  useEffect(() => {
    let cancelled = false
    const storedSessionId = decisionStorageKey
      ? window.localStorage.getItem(decisionStorageKey)
      : window.localStorage.getItem(latestStorageKey)

    setAnswer('')
    setError('')
    setSession(null)
    setCompletionItem(null)
    setCompletionFeedback(null)
    setSelectedCompletionOption('')
    setRestoring(false)

    if (!storedSessionId) return

    const parsedSessionId = Number(storedSessionId)
    if (!Number.isFinite(parsedSessionId)) return

    setRestoring(true)
    void getSocraticSession(userId, parsedSessionId, courseId)
      .then((restoredSession) => {
        if (!cancelled) setSession(restoredSession)
      })
      .catch(() => {
        window.localStorage.removeItem(latestStorageKey)
        if (decisionStorageKey) window.localStorage.removeItem(decisionStorageKey)
      })
      .finally(() => {
        if (!cancelled) setRestoring(false)
      })

    return () => {
      cancelled = true
    }
  }, [courseId, decisionStorageKey, latestStorageKey, userId])

  const canStart = response ? canStartSocraticSession(response) : false
  const conceptName =
    session?.concept_snapshot?.concept_name ??
    response?.decision.concept_state_snapshot?.concept_name ??
    'current concept'

  async function handleStartSocratic() {
    if (!response) return

    setBusy(true)
    setError('')
    try {
      const startedSession = await startSocraticSession(
        userId,
        response.decision.query,
        courseId,
        response.decision.decision_id,
        topK,
        3,
      )
      setSession(startedSession)
      setAnswer('')
      setCompletionItem(null)
      setCompletionFeedback(null)
      setSelectedCompletionOption('')
      window.localStorage.setItem(latestStorageKey, String(startedSession.id))
      if (decisionStorageKey) {
        window.localStorage.setItem(decisionStorageKey, String(startedSession.id))
      }
    } catch (socraticError) {
      setError(getErrorMessage(socraticError))
    } finally {
      setBusy(false)
    }
  }

  async function handleSubmitAnswer(event: FormEvent) {
    event.preventDefault()
    if (!session || !answer.trim()) return

    setBusy(true)
    setError('')
    try {
      const updatedSession = await respondToSocraticSession(
        userId,
        session.id,
        answer.trim(),
        courseId,
      )
      setSession(updatedSession)
      setAnswer('')
      window.localStorage.setItem(latestStorageKey, String(updatedSession.id))
    } catch (socraticError) {
      setError(getErrorMessage(socraticError))
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateCompletionCheck() {
    if (!session || session.status !== 'completed') return

    setCompletionBusy(true)
    setError('')
    try {
      const result = await createSocraticCompletionCheck(
        userId,
        session.id,
        courseId,
      )
      setSession(result.session)
      setCompletionItem(result.item)
      setCompletionFeedback(null)
      setSelectedCompletionOption('')
      window.localStorage.setItem(latestStorageKey, String(result.session.id))
    } catch (completionError) {
      setError(getErrorMessage(completionError))
    } finally {
      setCompletionBusy(false)
    }
  }

  async function handleSubmitCompletionAttempt() {
    if (!session || !selectedCompletionOption) return

    setCompletionBusy(true)
    setError('')
    try {
      const result = await submitSocraticCompletionAttempt(
        userId,
        session.id,
        selectedCompletionOption,
        courseId,
      )
      setSession(result.session)
      setCompletionFeedback(result.attempt)
      window.localStorage.setItem(latestStorageKey, String(result.session.id))
      await onOutcomeRecorded()
    } catch (completionError) {
      setError(getErrorMessage(completionError))
    } finally {
      setCompletionBusy(false)
    }
  }

  if (!session && !response) {
    return restoring ? (
      <div className="answer-card socratic-card">
        <div className="panel-body">
          <div className="badge-row">
            <span className="badge info">restoring guided session</span>
          </div>
        </div>
      </div>
    ) : null
  }

  if (!session) {
    if (!canStart && !error) return null

    return (
      <div className="answer-card socratic-card">
        <div className="panel-header">
          <h3 className="panel-title">
            <MessagesSquare size={18} aria-hidden="true" />
            Guided Learning
          </h3>
          <span className="badge info">bounded</span>
        </div>
        <div className="panel-body stack">
          <p className="muted">
            Start a short step-by-step session for {conceptName}. The tutor will ask
            one diagnostic question, then guide you with at most two hints.
          </p>
          {error && <div className="error">{error}</div>}
          <div className="quiz-actions">
            <button
              className="button secondary"
              disabled={busy || !canStart}
              onClick={() => void handleStartSocratic()}
              type="button"
            >
              {busy ? (
                <Loader2 className="spin" size={16} aria-hidden="true" />
              ) : (
                <MessagesSquare size={16} aria-hidden="true" />
              )}
              Guide me step by step
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="answer-card socratic-card">
      <div className="panel-header">
        <h3 className="panel-title">
          <MessagesSquare size={18} aria-hidden="true" />
          Guided Learning
        </h3>
        <div className="badge-row">
          <span className={`badge ${socraticStatusBadgeClass(session.status)}`}>
            {session.status}
          </span>
          <span className="badge info">{formatSocraticStage(session.current_stage)}</span>
        </div>
      </div>
      <div className="panel-body stack">
        <div className="item-topline">
          <div>
            <span className="field-label">Concept</span>
            <h4 className="item-title">{conceptName}</h4>
          </div>
          <span className="badge">{socraticProgressLabel(session)}</span>
        </div>

        {session.assessment && (
          <div className="attempt-feedback">
            <strong>{formatSocraticAssessment(session.assessment)}</strong>
            {session.assessment_reason && <p>{session.assessment_reason}</p>}
          </div>
        )}

        <div className="socratic-transcript">
          {session.turns.map((turn) => (
            <div className="socratic-turn" key={turn.id}>
              <div className="socratic-message tutor-message">
                <span className="field-label">{formatSocraticStage(turn.stage)}</span>
                <p>{turn.tutor_message}</p>
              </div>
              {turn.student_response && (
                <div className="socratic-message learner-message">
                  <span className="field-label">Your answer</span>
                  <p>{turn.student_response}</p>
                </div>
              )}
              {turn.assessment && (
                <div className="badge-row">
                  <span className={`badge ${socraticAssessmentBadgeClass(turn.assessment)}`}>
                    {formatSocraticAssessment(turn.assessment)}
                  </span>
                  {turn.assessment_reason && (
                    <span className="muted small">{turn.assessment_reason}</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {error && <div className="error">{error}</div>}

        {session.status === 'active' ? (
          <form className="stack" onSubmit={handleSubmitAnswer}>
            <label>
              <span className="field-label">Your answer</span>
              <textarea
                className="textarea socratic-input"
                disabled={busy}
                onChange={(event) => setAnswer(event.target.value)}
                placeholder="Answer in your own words..."
                value={answer}
              />
            </label>
            <div className="quiz-actions">
              <button
                className="button"
                disabled={busy || !answer.trim()}
                type="submit"
              >
                {busy ? (
                  <Loader2 className="spin" size={16} aria-hidden="true" />
                ) : (
                  <Send size={16} aria-hidden="true" />
                )}
                Submit answer
              </button>
            </div>
          </form>
        ) : (
          <div className="stack">
            <div className="notice">
              Session completed. Use one objective check to update learning progress
              for this concept.
            </div>
            {completionItem ? (
              <div className="item-row quiz-card">
                <div className="item-topline">
                  <h4 className="item-title">{completionItem.question}</h4>
                  <div className="badge-row">
                    <span className="badge info">socratic completion check</span>
                    <span
                      className={`badge ${traceBadgeClass(
                        completionItem.traceability_label,
                      )}`}
                    >
                      {completionItem.traceability_label}
                    </span>
                  </div>
                </div>
                <div
                  className="option-list"
                  role="group"
                  aria-label="Socratic completion check options"
                >
                  {completionItem.options.map((option) => {
                    const isSelected = selectedCompletionOption === option.id
                    const isCorrect = completionFeedback?.correct_option_id === option.id
                    const isIncorrectSelection =
                      completionFeedback?.selected_option_id === option.id &&
                      !completionFeedback.is_correct
                    return (
                      <button
                        className={[
                          'option-button',
                          isSelected ? 'selected' : '',
                          isCorrect ? 'correct' : '',
                          isIncorrectSelection ? 'incorrect' : '',
                        ]
                          .filter(Boolean)
                          .join(' ')}
                        disabled={Boolean(completionFeedback) || completionBusy}
                        key={option.id}
                        onClick={() => setSelectedCompletionOption(option.id)}
                        type="button"
                      >
                        <span className="option-letter">{option.id}</span>
                        <span>{option.text}</span>
                      </button>
                    )
                  })}
                </div>
                <div className="quiz-actions">
                  <button
                    className="button secondary"
                    disabled={
                      !selectedCompletionOption ||
                      Boolean(completionFeedback) ||
                      completionBusy
                    }
                    onClick={() => void handleSubmitCompletionAttempt()}
                    type="button"
                  >
                    {completionBusy ? (
                      <Loader2 className="spin" size={16} aria-hidden="true" />
                    ) : (
                      <CheckCircle2 size={16} aria-hidden="true" />
                    )}
                    {completionFeedback ? 'Progress updated' : 'Submit check'}
                  </button>
                </div>
                {completionFeedback && (
                  <div
                    className={`attempt-feedback ${
                      completionFeedback.is_correct ? 'correct' : 'incorrect'
                    }`}
                  >
                    <strong>
                      {completionFeedback.is_correct ? 'Correct' : 'Not quite'}
                    </strong>
                    <span>
                      Correct answer: {completionFeedback.correct_option_id}.{' '}
                      {completionFeedback.correct_option_text}
                    </span>
                    <p>{completionFeedback.explanation}</p>
                  </div>
                )}
                {completionItem.evidence_quote && (
                  <p className="quote">{completionItem.evidence_quote}</p>
                )}
              </div>
            ) : session.completion_quiz_attempt_id ? (
              <div className="notice">
                Completion check already recorded for this session.
              </div>
            ) : (
              <div className="quiz-actions">
                <button
                  className="button secondary"
                  disabled={completionBusy}
                  onClick={() => void handleCreateCompletionCheck()}
                  type="button"
                >
                  {completionBusy ? (
                    <Loader2 className="spin" size={16} aria-hidden="true" />
                  ) : (
                    <CheckCircle2 size={16} aria-hidden="true" />
                  )}
                  Check my understanding
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function TutorDecisionPanel({ response }: { response: TutorResponse | null }) {
  return (
    <aside className="panel">
      <div className="panel-header">
        <h3 className="panel-title">
          <Gauge size={18} aria-hidden="true" />
          Decision
        </h3>
        {response && (
          <span className="badge info">{response.decision.policy_version}</span>
        )}
      </div>
      <div className="panel-body stack">
        {!response ? (
          <EmptyState label="No tutor decision yet" />
        ) : (
          <>
            <div className="decision-summary">
              <div>
                <span className="field-label">Action</span>
                <strong>{response.decision.selected_action}</strong>
              </div>
              <div>
                <span className="field-label">Strategy</span>
                <strong>{response.decision.response_strategy}</strong>
              </div>
              <div>
                <span className="field-label">Intent</span>
                <strong>{response.decision.detected_intent}</strong>
              </div>
              <div>
                <span className="field-label">Reason</span>
                <strong>{response.decision.primary_reason}</strong>
              </div>
              <div>
                <span className="field-label">Scope</span>
                <strong>{response.decision.learner_state_scope}</strong>
              </div>
            </div>
            <p className="quote">{response.decision.teaching_reason}</p>
            <TutorLearnerSnapshot response={response} />
            <TutorConceptSnapshot response={response} />
            <TutorMisconceptionSnapshot response={response} />
            <TutorEvidenceSnapshot response={response} />
            {response.sources.length > 0 && (
              <div className="source-box list">
                {response.sources.map((source) => (
                  <div className="item-row compact" key={source.chunk_id}>
                    <div className="item-topline">
                      <h4 className="item-title">{source.filename}</h4>
                      <span className="badge">
                        {Math.round(source.similarity * 100)}%
                      </span>
                    </div>
                    <p className="muted small">{source.content.slice(0, 320)}</p>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  )
}

function TutorConceptSnapshot({ response }: { response: TutorResponse }) {
  const state = response.decision.concept_state_snapshot
  if (!state) return null

  return (
    <div className="concept-snapshot">
      <div className="item-topline">
        <div>
          <span className="field-label">Concept</span>
          <h4 className="item-title">{state.concept_name}</h4>
        </div>
        <span className={`badge ${state.state_status === 'observed' ? 'good' : 'info'}`}>
          {state.state_status}
        </span>
      </div>
      <div className="snapshot-grid compact">
        <Metric
          label="Mastery"
          value={
            state.mastery_score == null
              ? 'Unknown'
              : `${Math.round(state.mastery_score * 100)}%`
          }
        />
        <Metric
          label="Accuracy"
          value={
            state.recent_accuracy == null
              ? 'Unknown'
              : `${Math.round(state.recent_accuracy * 100)}%`
          }
        />
        <Metric label="Attempts" value={state.attempt_count} />
        <Metric label="Attention" value={state.needs_attention ? 'Yes' : 'No'} />
      </div>
    </div>
  )
}

function TutorMisconceptionSnapshot({ response }: { response: TutorResponse }) {
  const misconception = response.decision.misconception_snapshot
  if (!misconception) return null

  return (
    <div className="concept-snapshot">
      <div className="item-topline">
        <div>
          <span className="field-label">Learning signal</span>
          <h4 className="item-title">
            {misconception.misconception_type.replace(/_/g, ' ')}
          </h4>
        </div>
        <span className="badge info">
          {Math.round(misconception.confidence * 100)}%
        </span>
      </div>
      <p className="muted small">{misconception.description}</p>
    </div>
  )
}

function TutorLearnerSnapshot({ response }: { response: TutorResponse }) {
  const state = response.decision.learner_state_snapshot
  const conceptState = response.decision.concept_state_snapshot
  const isUnobservedConcept =
    response.decision.learner_state_scope === 'concept' &&
    conceptState?.state_status === 'unobserved'

  return (
    <div className="snapshot-grid">
      <Metric
        label="Mastery"
        value={
          isUnobservedConcept
            ? 'Unknown'
            : `${Math.round(state.mastery_score * 100)}%`
        }
      />
      <Metric
        label="Accuracy"
        value={
          isUnobservedConcept
            ? 'Unknown'
            : `${Math.round(state.recent_accuracy * 100)}%`
        }
      />
      <Metric label="Attempts" value={state.attempt_count} />
      <Metric label="Errors" value={state.consecutive_errors} />
    </div>
  )
}

function TutorEvidenceSnapshot({ response }: { response: TutorResponse }) {
  const evidence = response.decision.evidence_state_snapshot
  return (
    <div className="evidence-snapshot">
      <div className="badge-row">
        <span className={`badge ${evidenceBadgeClass(evidence.evidence_strength)}`}>
          evidence {evidence.evidence_strength}
        </span>
        <span className="badge">
          coverage {Math.round(evidence.source_coverage * 100)}%
        </span>
        <span className="badge">
          top {Math.round(evidence.top_similarity * 100)}%
        </span>
        <span className="badge">{evidence.retrieved_chunk_count} chunks</span>
        <span className="badge">{evidence.retrieval_scope}</span>
      </div>
      <p className="muted small">{evidence.reason}</p>
    </div>
  )
}

function TutorQuizItems({
  courseId,
  decisionId,
  items,
  onOutcomeLinked,
  userId,
}: {
  courseId: number | null
  decisionId: number
  items: QuizItem[]
  onOutcomeLinked: () => Promise<void>
  userId: string
}) {
  const [selectedOptions, setSelectedOptions] = useState<Record<number, string>>({})
  const [attemptFeedback, setAttemptFeedback] = useState<Record<number, QuizAttemptResponse>>(
    {},
  )
  const [busyItemId, setBusyItemId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    setSelectedOptions({})
    setAttemptFeedback({})
    setBusyItemId(null)
    setError('')
    setNotice('')
  }, [decisionId])

  async function handleSubmitAttempt(item: QuizItem) {
    const selectedOptionId = selectedOptions[item.id]
    if (!selectedOptionId) return

    setBusyItemId(item.id)
    setError('')
    setNotice('')
    try {
      const feedback = await submitQuizAttempt(
        userId,
        item.id,
        selectedOptionId,
        courseId,
      )
      await linkTutorOutcome(decisionId, {
        outcome_type: 'quiz_attempt',
        quiz_attempt_id: feedback.id,
      })
      setAttemptFeedback((current) => ({ ...current, [item.id]: feedback }))
      setNotice('Outcome linked to this tutor decision.')
      await onOutcomeLinked()
    } catch (attemptError) {
      setError(getErrorMessage(attemptError))
    } finally {
      setBusyItemId(null)
    }
  }

  const isComprehensionCheck =
    items.length > 0 && items.every((item) => item.origin === 'comprehension_check')
  const title = isComprehensionCheck ? 'Check your understanding' : 'Generated Practice'

  return (
    <div className="stack">
      <h3 className="section-title">{title}</h3>
      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}
      <div className="list">
        {items.map((item) => {
          const selectedOptionId = selectedOptions[item.id]
          const feedback = attemptFeedback[item.id]
          const hasOptions = item.options.length > 0
          return (
            <div className="item-row quiz-card" key={item.id}>
              <div className="item-topline">
                <h4 className="item-title">{item.question}</h4>
                <div className="badge-row">
                  {item.origin === 'comprehension_check' && (
                    <span className="badge info">comprehension check</span>
                  )}
                  <span className={`badge ${traceBadgeClass(item.traceability_label)}`}>
                    {item.traceability_label}
                  </span>
                </div>
              </div>
              {hasOptions ? (
                <div className="option-list" role="group" aria-label="Tutor answer options">
                  {item.options.map((option) => {
                    const isSelected = selectedOptionId === option.id
                    const isCorrect = feedback?.correct_option_id === option.id
                    const isIncorrectSelection =
                      feedback?.selected_option_id === option.id && !feedback.is_correct
                    return (
                      <button
                        className={[
                          'option-button',
                          isSelected ? 'selected' : '',
                          isCorrect ? 'correct' : '',
                          isIncorrectSelection ? 'incorrect' : '',
                        ]
                          .filter(Boolean)
                          .join(' ')}
                        disabled={Boolean(feedback)}
                        key={option.id}
                        onClick={() =>
                          setSelectedOptions((current) => ({
                            ...current,
                            [item.id]: option.id,
                          }))
                        }
                        type="button"
                      >
                        <span className="option-letter">{option.id}</span>
                        <span>{option.text}</span>
                      </button>
                    )
                  })}
                </div>
              ) : (
                <p className="answer">{item.answer}</p>
              )}

              {hasOptions && (
                <div className="quiz-actions">
                  <button
                    className="button secondary"
                    disabled={
                      !selectedOptionId ||
                      Boolean(feedback) ||
                      busyItemId === item.id
                    }
                    onClick={() => void handleSubmitAttempt(item)}
                    type="button"
                  >
                    {busyItemId === item.id ? (
                      <Loader2 className="spin" size={16} aria-hidden="true" />
                    ) : (
                      <CheckCircle2 size={16} aria-hidden="true" />
                    )}
                    {feedback ? 'Outcome recorded' : 'Submit answer'}
                  </button>
                </div>
              )}

              {feedback && (
                <div
                  className={`attempt-feedback ${
                    feedback.is_correct ? 'correct' : 'incorrect'
                  }`}
                >
                  <strong>{feedback.is_correct ? 'Correct' : 'Not quite'}</strong>
                  <span>
                    Correct answer: {feedback.correct_option_id}.{' '}
                    {feedback.correct_option_text}
                  </span>
                  <p>{feedback.explanation}</p>
                </div>
              )}

              <div className="badge-row">
                <span className="badge">{item.difficulty}</span>
                <span className="badge">{item.question_type}</span>
                {item.source_chunk_ids.map((id) => (
                  <span className="badge" key={id}>
                    chunk {id}
                  </span>
                ))}
              </div>
              {item.evidence_quote && <p className="quote">{item.evidence_quote}</p>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TutorReviewItems({
  courseId,
  decisionId,
  items,
  onOutcomeLinked,
  userId,
}: {
  courseId: number | null
  decisionId: number
  items: DueReviewItem[]
  onOutcomeLinked: () => Promise<void>
  userId: string
}) {
  const [busyItemId, setBusyItemId] = useState<number | null>(null)
  const [completedItems, setCompletedItems] = useState<Record<number, number>>({})
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    setBusyItemId(null)
    setCompletedItems({})
    setError('')
    setNotice('')
  }, [decisionId])

  async function handleReview(itemId: number, rating: number, isCorrect: boolean) {
    setBusyItemId(itemId)
    setError('')
    setNotice('')
    try {
      const review = await submitReview(userId, itemId, rating, isCorrect, courseId)
      await linkTutorOutcome(decisionId, {
        outcome_type: 'review',
        review_record_id: review.id,
      })
      setCompletedItems((current) => ({ ...current, [itemId]: rating }))
      setNotice('Review outcome linked to this tutor decision.')
      await onOutcomeLinked()
    } catch (reviewError) {
      setError(getErrorMessage(reviewError))
    } finally {
      setBusyItemId(null)
    }
  }

  return (
    <div className="stack">
      <h3 className="section-title">Due Review</h3>
      {error && <div className="error">{error}</div>}
      {notice && <div className="notice">{notice}</div>}
      <div className="list">
        {items.map(({ item, latest_review }) => (
          <div className="item-row compact" key={item.id}>
            <div className="item-topline">
              <h4 className="item-title">{item.question}</h4>
              <span className={`badge ${completedItems[item.id] ? 'good' : 'warn'}`}>
                {completedItems[item.id] ? 'recorded' : 'due'}
              </span>
            </div>
            <p className="answer">{item.answer}</p>
            <div className="review-actions">
              {[1, 2, 3, 4].map((rating) => (
                <button
                  className={rating >= 3 ? 'button secondary' : 'button ghost'}
                  disabled={busyItemId === item.id || Boolean(completedItems[item.id])}
                  key={rating}
                  onClick={() => void handleReview(item.id, rating, rating >= 3)}
                  type="button"
                >
                  {busyItemId === item.id ? (
                    <Loader2 className="spin" size={15} aria-hidden="true" />
                  ) : (
                    rating
                  )}
                </button>
              ))}
            </div>
            <div className="badge-row">
              <span className="badge">{item.difficulty}</span>
              {latest_review && (
                <span className="badge">rating {latest_review.rating}</span>
              )}
              {latest_review?.due_at && (
                <span className="badge">{formatDate(latest_review.due_at)}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function TutorClaims({ response }: { response: TutorResponse }) {
  return (
    <div className="stack">
      <h3 className="section-title">Claims</h3>
      <div className="list">
        {response.claims.map((claim, index) => (
          <div className={`claim-card ${claim.support_level}`} key={`${claim.claim}-${index}`}>
            <div className="item-topline">
              <h4 className="item-title">{claim.claim}</h4>
              <span className={`badge ${supportBadgeClass(claim.support_level)}`}>
                {claim.support_level}
              </span>
            </div>
            <div className="badge-row">
              {claim.source_chunk_ids.map((id) => (
                <span className="badge" key={id}>
                  chunk {id}
                </span>
              ))}
            </div>
            {claim.evidence_quote && <p className="quote">{claim.evidence_quote}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}

function DocumentsView({
  courseId,
  courseName,
  documents,
  userId,
  onUploaded,
}: {
  courseId: number | null
  courseName: string | null
  documents: DocumentItem[]
  userId: string
  onUploaded: () => Promise<void>
}) {
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState('')

  async function handleUpload(event: FormEvent) {
    event.preventDefault()
    if (files.length === 0) return

    setBusy(true)
    setError('')
    try {
      for (const file of files) {
        await uploadDocument(userId, file, courseId)
      }
      setFiles([])
      await onUploaded()
    } catch (uploadError) {
      setError(getErrorMessage(uploadError))
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(document: DocumentItem) {
    const confirmed = window.confirm(`Delete "${document.filename}" from the library?`)
    if (!confirmed) return

    setDeletingId(document.id)
    setError('')
    try {
      await deleteDocument(userId, document.id)
      await onUploaded()
    } catch (deleteError) {
      setError(getErrorMessage(deleteError))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="grid two">
      <section className="panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <FileUp size={18} aria-hidden="true" />
            Upload
          </h3>
          <span className="badge info">{courseName ?? 'All materials'}</span>
        </div>
        <div className="panel-body">
          <form className="stack" onSubmit={handleUpload}>
            <label className="file-input">
              <span className="field-label">Course materials</span>
              <input
                accept=".pdf,.pptx,.docx,.txt,.md"
                multiple
                onChange={(event) =>
                  setFiles(Array.from(event.target.files ?? []))
                }
                type="file"
              />
              {files.length > 0 && (
                <span className="muted small">
                  {files.length} file{files.length === 1 ? '' : 's'} selected
                </span>
              )}
            </label>
            {error && <div className="error">{error}</div>}
            <button className="button" disabled={files.length === 0 || busy} type="submit">
              {busy ? (
                <Loader2 className="spin" size={16} aria-hidden="true" />
              ) : (
                <Upload size={16} aria-hidden="true" />
              )}
              Upload {files.length > 1 ? `${files.length} files` : 'files'}
            </button>
          </form>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <Library size={18} aria-hidden="true" />
            Library
          </h3>
          <span className="badge info">{documents.length} files</span>
        </div>
        <div className="panel-body">
          {documents.length === 0 ? (
            <EmptyState label="No documents" />
          ) : (
            <div className="list">
              {documents.map((document) => (
                <div className="item-row" key={document.id}>
                  <div className="item-topline">
                    <h4 className="item-title">{document.filename}</h4>
                    <div className="item-actions">
                      <span
                        className={`badge ${document.status === 'done' ? 'good' : 'warn'}`}
                      >
                        {document.status}
                      </span>
                      <button
                        aria-label={`Delete ${document.filename}`}
                        className="icon-button danger"
                        disabled={deletingId === document.id}
                        onClick={() => void handleDelete(document)}
                        title="Delete document"
                        type="button"
                      >
                        {deletingId === document.id ? (
                          <Loader2 className="spin" size={16} aria-hidden="true" />
                        ) : (
                          <Trash2 size={16} aria-hidden="true" />
                        )}
                      </button>
                    </div>
                  </div>
                  <div className="badge-row">
                    <span className="badge">{document.file_type}</span>
                    <span className="badge">{document.chunk_count} chunks</span>
                    {document.course_id && (
                      <span className="badge">course {document.course_id}</span>
                    )}
                    <span className="badge">{formatDate(document.created_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function ChatView({ courseId, userId }: { courseId: number | null; userId: string }) {
  const [query, setQuery] = useState('What is artificial intelligence?')
  const [topK, setTopK] = useState(5)
  const [mode, setMode] = useState<'grounded' | 'compare'>('grounded')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [answer, setAnswer] = useState<ChatResponse | null>(null)
  const [comparison, setComparison] = useState<ChatCompareResponse | null>(null)
  const [evaluation, setEvaluation] = useState<AnswerEvaluation | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!query.trim()) return

    setBusy(true)
    setError('')
    setAnswer(null)
    setComparison(null)
    setEvaluation(null)
    try {
      if (mode === 'compare') {
        const result = await compareChat(userId, query, topK, courseId)
        setComparison(result)
        setEvaluation(await evaluateAnswer(result.grounded, true, userId, courseId))
      } else {
        const result = await chat(userId, query, topK, courseId)
        setAnswer(result)
        setEvaluation(await evaluateAnswer(result, true, userId, courseId))
      }
    } catch (chatError) {
      setError(getErrorMessage(chatError))
    } finally {
      setBusy(false)
    }
  }

  const activeAnswer = comparison?.grounded ?? answer

  return (
    <div className="grid two">
      <section className="panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <MessageSquareText size={18} aria-hidden="true" />
            Ask
          </h3>
          <div className="toolbar">
            <select
              className="select"
              value={mode}
              onChange={(event) => setMode(event.target.value as 'grounded' | 'compare')}
            >
              <option value="grounded">Grounded</option>
              <option value="compare">Compare</option>
            </select>
          </div>
        </div>
        <div className="panel-body stack">
          <form className="stack" onSubmit={handleSubmit}>
            <textarea
              className="textarea"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <div className="form-row">
              <label>
                <span className="field-label">Top K</span>
                <input
                  className="input"
                  max={10}
                  min={1}
                  onChange={(event) => setTopK(Number(event.target.value))}
                  type="number"
                  value={topK}
                />
              </label>
              <div />
              <button className="button" disabled={busy || !query.trim()} type="submit">
                {busy ? <Loader2 size={16} aria-hidden="true" /> : <Send size={16} />}
                Run
              </button>
            </div>
          </form>
          {error && <div className="error">{error}</div>}
          {evaluation && <AnswerMetrics evaluation={evaluation} />}
          {comparison ? (
            <div className="compare-grid">
              <AnswerPanel title="Grounded" response={comparison.grounded} />
              <AnswerPanel title="Ungrounded" response={comparison.ungrounded} />
            </div>
          ) : (
            answer && <AnswerPanel title="Grounded Answer" response={answer} />
          )}
        </div>
      </section>

      <EvidenceInspector response={activeAnswer} />
    </div>
  )
}

function ProgressView({
  courseId,
  courseName,
  userId,
}: {
  courseId: number | null
  courseName: string | null
  userId: string
}) {
  const [progress, setProgress] = useState<CourseProgress | null>(null)
  const [selectedConceptId, setSelectedConceptId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const selectedConcept = useMemo(() => {
    if (!progress) return null
    return (
      progress.concepts.find((concept) => concept.concept_id === selectedConceptId) ??
      progress.concepts[0] ??
      null
    )
  }, [progress, selectedConceptId])

  const loadProgress = useCallback(async () => {
    if (courseId == null) {
      setProgress(null)
      setSelectedConceptId(null)
      setError('')
      return
    }

    setBusy(true)
    setError('')
    try {
      const result = await getCourseProgress(userId, courseId)
      setProgress(result)
      setSelectedConceptId((current) =>
        current != null &&
        result.concepts.some((concept) => concept.concept_id === current)
          ? current
          : (result.concepts[0]?.concept_id ?? null),
      )
    } catch (progressError) {
      setError(getErrorMessage(progressError))
    } finally {
      setBusy(false)
    }
  }, [courseId, userId])

  useEffect(() => {
    void loadProgress()
  }, [loadProgress])

  if (courseId == null) {
    return (
      <section className="panel">
        <div className="panel-body">
          <EmptyState label="Select a course workspace to view concept progress." />
        </div>
      </section>
    )
  }

  return (
    <div className="grid two">
      <section className="panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <BarChart3 size={18} aria-hidden="true" />
            Course Progress
          </h3>
          <div className="toolbar">
            <span className="badge info">{courseName ?? `Course ${courseId}`}</span>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => void loadProgress()}
              type="button"
            >
              {busy ? (
                <Loader2 className="spin" size={16} aria-hidden="true" />
              ) : (
                <RefreshCw size={16} aria-hidden="true" />
              )}
              Refresh
            </button>
          </div>
        </div>
        <div className="panel-body stack">
          {error && <div className="error">{error}</div>}
          {busy && !progress ? (
            <EmptyState label="Loading course progress..." />
          ) : !progress || progress.concepts.length === 0 ? (
            <EmptyState label="No concept progress yet. Extract concepts from your course materials first." />
          ) : (
            <>
              <ProgressOverview progress={progress} />
              <div className="progress-card-grid">
                {progress.concepts.map((concept) => (
                  <button
                    className={`progress-card ${
                      selectedConcept?.concept_id === concept.concept_id
                        ? 'selected'
                        : ''
                    }`}
                    key={concept.concept_id}
                    onClick={() => setSelectedConceptId(concept.concept_id)}
                    type="button"
                  >
                    <div className="item-topline">
                      <h4 className="item-title">{concept.concept_name}</h4>
                      <span className={`badge ${progressStatusBadgeClass(concept.status)}`}>
                        {formatProgressStatus(concept.status)}
                      </span>
                    </div>
                    <div className="metric-strip compact">
                      <Metric
                        label="Estimated mastery"
                        value={formatNullablePercent(concept.mastery_score)}
                      />
                      <Metric
                        label="Recent accuracy"
                        value={formatNullablePercent(concept.recent_accuracy)}
                      />
                      <Metric label="Attempts" value={concept.attempt_count} />
                      <Metric
                        label="Review"
                        value={concept.review_due ? 'Due' : 'Not due'}
                      />
                    </div>
                    {concept.latest_misconception && (
                      <p className="muted small">
                        Learning signal: {concept.latest_misconception.description}
                      </p>
                    )}
                    {concept.status === 'unobserved' && (
                      <p className="muted small">No learning evidence yet.</p>
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </section>

      <ProgressDetailPanel concept={selectedConcept} />
    </div>
  )
}

function ProgressOverview({ progress }: { progress: CourseProgress }) {
  const summary = progress.summary
  return (
    <div className="metric-strip progress-overview">
      <Metric label="Concepts" value={summary.total_concepts} />
      <Metric label="Observed" value={summary.observed_concepts} />
      <Metric label="Unobserved" value={summary.unobserved_concepts} />
      <Metric label="Need attention" value={summary.needs_attention_count} />
      <Metric label="Reviews due" value={summary.review_due_count} />
      <Metric label="Strong" value={summary.strong_count} />
      <Metric label="Guided sessions" value={summary.socratic_completed_count} />
      <Metric
        label="Completion checks"
        value={summary.socratic_completion_attempt_count}
      />
    </div>
  )
}

function ProgressDetailPanel({
  concept,
}: {
  concept: CourseProgress['concepts'][number] | null
}) {
  return (
    <aside className="panel">
      <div className="panel-header">
        <h3 className="panel-title">
          <Gauge size={18} aria-hidden="true" />
          Concept Detail
        </h3>
        {concept && (
          <span className={`badge ${progressStatusBadgeClass(concept.status)}`}>
            {formatProgressStatus(concept.status)}
          </span>
        )}
      </div>
      <div className="panel-body stack">
        {!concept ? (
          <EmptyState label="Select a concept to inspect progress." />
        ) : (
          <>
            <div>
              <span className="field-label">Concept</span>
              <h3 className="detail-title">{concept.concept_name}</h3>
            </div>
            <div className="snapshot-grid">
              <Metric
                label="Estimated mastery"
                value={formatNullablePercent(concept.mastery_score)}
              />
              <Metric
                label="Recent accuracy"
                value={formatNullablePercent(concept.recent_accuracy)}
              />
              <Metric label="Attempts" value={concept.attempt_count} />
              <Metric label="Errors" value={concept.consecutive_errors} />
            </div>
            <div className="evidence-snapshot">
              <div className="badge-row">
                <span className={`badge ${progressStatusBadgeClass(concept.status)}`}>
                  {formatProgressStatus(concept.status)}
                </span>
                <span className={`badge ${concept.review_due ? 'warn' : 'info'}`}>
                  {concept.review_due ? 'review due' : 'review not due'}
                </span>
                <span className="badge">
                  {concept.state_status === 'unobserved'
                    ? 'unobserved'
                    : 'observed'}
                </span>
              </div>
              {concept.attention_reasons.length > 0 ? (
                <div className="badge-row">
                  {concept.attention_reasons.map((reason) => (
                    <span className="badge warn" key={reason}>
                      {formatAttentionReason(reason)}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="muted small">
                  {concept.status === 'unobserved'
                    ? 'No learning evidence has been recorded for this concept yet.'
                    : 'No current attention signal.'}
                </p>
              )}
            </div>

            <div className="concept-snapshot">
              <div className="item-topline">
                <div>
                  <span className="field-label">Learning signal</span>
                  <h4 className="item-title">
                    {concept.latest_misconception
                      ? formatMisconceptionType(
                          concept.latest_misconception.misconception_type,
                        )
                      : 'No recent signal'}
                  </h4>
                </div>
                {concept.latest_misconception && (
                  <span className="badge info">
                    {Math.round(concept.latest_misconception.confidence * 100)}%
                  </span>
                )}
              </div>
              <p className="muted small">
                {concept.latest_misconception
                  ? concept.latest_misconception.description
                  : 'No high-confidence misconception has been detected recently.'}
              </p>
            </div>

            <div className="concept-snapshot">
              <span className="field-label">Prerequisites</span>
              {concept.prerequisites.length > 0 ? (
                <div className="badge-row">
                  {concept.prerequisites.map((prerequisite) => (
                    <span className="badge" key={prerequisite.id}>
                      {prerequisite.name}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="muted small">No prerequisite concepts recorded.</p>
              )}
            </div>

            <div className="concept-snapshot">
              <span className="field-label">Guided learning activity</span>
              <div className="snapshot-grid compact">
                <Metric
                  label="Sessions"
                  value={concept.socratic_activity.completed_sessions}
                />
                <Metric
                  label="Checks"
                  value={concept.socratic_activity.completion_attempts}
                />
                <Metric
                  label="Latest check"
                  value={formatCompletionCheck(concept)}
                />
                <Metric
                  label="Latest session"
                  value={
                    concept.socratic_activity.latest_completed_at
                      ? formatDate(concept.socratic_activity.latest_completed_at)
                      : 'None'
                  }
                />
              </div>
            </div>
          </>
        )}
      </div>
    </aside>
  )
}

function EvaluationView({
  courseId,
  userId,
}: {
  courseId: number | null
  userId: string
}) {
  const [query, setQuery] = useState('What is artificial intelligence?')
  const [expectedAnswerable, setExpectedAnswerable] = useState(true)
  const [topK, setTopK] = useState(5)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [comparison, setComparison] = useState<ChatCompareResponse | null>(null)
  const [groundedEvaluation, setGroundedEvaluation] =
    useState<AnswerEvaluation | null>(null)
  const [ungroundedEvaluation, setUngroundedEvaluation] =
    useState<AnswerEvaluation | null>(null)

  async function handleRun(event: FormEvent) {
    event.preventDefault()
    if (!query.trim()) return

    setBusy(true)
    setError('')
    setComparison(null)
    setGroundedEvaluation(null)
    setUngroundedEvaluation(null)
    try {
      const result = await compareChat(userId, query, topK, courseId)
      const [grounded, ungrounded] = await Promise.all([
        evaluateAnswer(result.grounded, expectedAnswerable, userId, courseId),
        evaluateAnswer(result.ungrounded, expectedAnswerable, userId, courseId),
      ])
      setComparison(result)
      setGroundedEvaluation(grounded)
      setUngroundedEvaluation(ungrounded)
    } catch (evaluationError) {
      setError(getErrorMessage(evaluationError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid two">
      <section className="panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <BarChart3 size={18} aria-hidden="true" />
            Experiment Case
          </h3>
          <span className="badge info">Grounded vs Ungrounded</span>
        </div>
        <div className="panel-body stack">
          <form className="stack" onSubmit={handleRun}>
            <textarea
              className="textarea"
              onChange={(event) => setQuery(event.target.value)}
              value={query}
            />
            <div className="form-row">
              <label>
                <span className="field-label">Expected</span>
                <select
                  className="select"
                  onChange={(event) =>
                    setExpectedAnswerable(event.target.value === 'true')
                  }
                  value={String(expectedAnswerable)}
                >
                  <option value="true">answerable</option>
                  <option value="false">unanswerable</option>
                </select>
              </label>
              <label>
                <span className="field-label">Top K</span>
                <input
                  className="input"
                  max={10}
                  min={1}
                  onChange={(event) => setTopK(Number(event.target.value))}
                  type="number"
                  value={topK}
                />
              </label>
              <button className="button" disabled={busy || !query.trim()} type="submit">
                {busy ? <Loader2 size={16} aria-hidden="true" /> : <SearchCheck size={16} />}
                Run
              </button>
            </div>
          </form>
          {error && <div className="error">{error}</div>}

          {groundedEvaluation && ungroundedEvaluation ? (
            <EvaluationMatrix
              grounded={groundedEvaluation}
              ungrounded={ungroundedEvaluation}
            />
          ) : (
            <EmptyState label="Run an experiment case to compare evidence-aware grounding." />
          )}
        </div>
      </section>

      {!comparison ? (
        <section className="panel">
          <div className="panel-header">
            <h3 className="panel-title">
              <Gauge size={18} aria-hidden="true" />
              Results
            </h3>
          </div>
          <div className="panel-body">
            <EmptyState label="No comparison result" />
          </div>
        </section>
      ) : (
        <div className="stack">
          <div className="compare-grid">
            <AnswerPanel title="Grounded" response={comparison.grounded} />
            <AnswerPanel title="Ungrounded" response={comparison.ungrounded} />
          </div>
          <EvidenceInspector response={comparison.grounded} />
        </div>
      )}
    </div>
  )
}

function EvaluationMatrix({
  grounded,
  ungrounded,
}: {
  grounded: AnswerEvaluation
  ungrounded: AnswerEvaluation
}) {
  const rows = [
    {
      label: 'Groundedness',
      grounded: `${Math.round(grounded.groundedness_score * 100)}%`,
      ungrounded: `${Math.round(ungrounded.groundedness_score * 100)}%`,
      direction: 'higher',
    },
    {
      label: 'Unsupported claims',
      grounded: `${Math.round(grounded.unsupported_claim_rate * 100)}%`,
      ungrounded: `${Math.round(ungrounded.unsupported_claim_rate * 100)}%`,
      direction: 'lower',
    },
    {
      label: 'Citation precision',
      grounded: formatEvaluationPercent(grounded.citation_precision),
      ungrounded: formatEvaluationPercent(ungrounded.citation_precision),
      direction: 'higher',
    },
    {
      label: 'Correct refusal',
      grounded: grounded.correct_refusal ? 'yes' : 'no',
      ungrounded: ungrounded.correct_refusal ? 'yes' : 'no',
      direction: 'higher',
    },
    {
      label: 'Claims',
      grounded: grounded.claim_count,
      ungrounded: ungrounded.claim_count,
      direction: 'context',
    },
  ]

  return (
    <div className="evaluation-matrix">
      <div className="evaluation-row header">
        <span>Metric</span>
        <span>Grounded</span>
        <span>Ungrounded</span>
      </div>
      {rows.map((row) => (
        <div className="evaluation-row" key={row.label}>
          <span>{row.label}</span>
          <strong className={row.direction === 'higher' ? 'metric-good' : ''}>
            {row.grounded}
          </strong>
          <strong className={row.direction === 'lower' ? 'metric-warn' : ''}>
            {row.ungrounded}
          </strong>
        </div>
      ))}
    </div>
  )
}

function AnswerPanel({ title, response }: { title: string; response: ChatResponse }) {
  return (
    <div className="answer-card">
      <div className="panel-header">
        <h3 className="panel-title">
          <SearchCheck size={18} aria-hidden="true" />
          {title}
        </h3>
        <span className={`badge ${response.answer_status === 'answered' ? 'good' : 'warn'}`}>
          {response.answer_status}
        </span>
      </div>
      <div className="panel-body stack">
        <div className="badge-row">
          <span className="badge info">{response.mode}</span>
          <span className={`badge ${evidenceBadgeClass(response.evidence_state.evidence_strength)}`}>
            evidence {response.evidence_state.evidence_strength}
          </span>
          <span className="badge">{Math.round(response.overall_groundedness * 100)}%</span>
          <span className="badge">{response.claims.length} claims</span>
        </div>
        <p className="answer">{response.answer}</p>
      </div>
    </div>
  )
}

function EvidenceInspector({ response }: { response: ChatResponse | null }) {
  return (
    <aside className="panel">
      <div className="panel-header">
        <h3 className="panel-title">
          <Gauge size={18} aria-hidden="true" />
          Evidence
        </h3>
        {response && (
          <span className={`badge ${evidenceBadgeClass(response.evidence_state.evidence_strength)}`}>
            {response.evidence_state.evidence_strength}
          </span>
        )}
      </div>
      <div className="panel-body stack">
        {!response ? (
          <EmptyState label="No answer selected" />
        ) : (
          <>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${Math.round(response.overall_groundedness * 100)}%` }}
              />
            </div>
            <div className="badge-row">
              <span className="badge info">{response.sources.length} sources</span>
              <span className="badge">
                {Math.round(response.evidence_state.source_coverage * 100)}% coverage
              </span>
              <span className="badge good">
                {response.evidence_state.supported_claim_count} supported
              </span>
              {response.evidence_state.unsupported_claim_count > 0 && (
                <span className="badge warn">
                  {response.evidence_state.unsupported_claim_count} unsupported
                </span>
              )}
              {response.evidence_state.contradicted_claim_count > 0 && (
                <span className="badge bad">
                  {response.evidence_state.contradicted_claim_count} contradicted
                </span>
              )}
            </div>
            <div className="list">
              {response.claims.map((claim, index) => (
                <div className={`claim-card ${claim.support_level}`} key={`${claim.claim}-${index}`}>
                  <div className="item-topline">
                    <h4 className="item-title">{claim.claim}</h4>
                    <span className={`badge ${supportBadgeClass(claim.support_level)}`}>
                      {claim.support_level}
                    </span>
                  </div>
                  <div className="badge-row">
                    {claim.source_chunk_ids.map((id) => (
                      <span className="badge" key={id}>
                        chunk {id}
                      </span>
                    ))}
                  </div>
                  {claim.evidence_quote && <p className="quote">{claim.evidence_quote}</p>}
                </div>
              ))}
            </div>
            <div className="source-box list">
              {response.sources.map((source) => (
                <div className="item-row compact" key={source.chunk_id}>
                  <div className="item-topline">
                    <h4 className="item-title">{source.filename}</h4>
                    <span className="badge">{Math.round(source.similarity * 100)}%</span>
                  </div>
                  <p className="muted small">{source.content.slice(0, 360)}</p>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </aside>
  )
}

function QuizView({
  courseId,
  items,
  materialCount,
  userId,
  onGenerated,
}: {
  courseId: number | null
  items: QuizItem[]
  materialCount: number
  userId: string
  onGenerated: () => Promise<void>
}) {
  const [focus, setFocus] = useState('')
  const [count, setCount] = useState(3)
  const [difficulty, setDifficulty] = useState('medium')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [generated, setGenerated] = useState<QuizItem[]>([])
  const [selectedOptions, setSelectedOptions] = useState<Record<number, string>>({})
  const [attemptFeedback, setAttemptFeedback] = useState<Record<number, QuizAttemptResponse>>(
    {},
  )
  const [attemptBusyId, setAttemptBusyId] = useState<number | null>(null)
  const [removalBusyId, setRemovalBusyId] = useState<number | null>(null)
  const [removalMessage, setRemovalMessage] = useState('')
  const [showGenerated, setShowGenerated] = useState(false)

  useEffect(() => {
    setGenerated([])
    setSelectedOptions({})
    setAttemptFeedback({})
    setRemovalMessage('')
    setError('')
    setShowGenerated(false)
  }, [courseId, userId])

  async function handleGenerate(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await generateQuiz(userId, focus, count, difficulty, 5, courseId)
      setGenerated(response.items)
      setSelectedOptions({})
      setAttemptFeedback({})
      setRemovalMessage('')
      setShowGenerated(true)
      await onGenerated()
    } catch (quizError) {
      setError(getErrorMessage(quizError))
    } finally {
      setBusy(false)
    }
  }

  const visibleItems = showGenerated ? generated : items

  async function handleSubmitAttempt(item: QuizItem) {
    const selectedOptionId = selectedOptions[item.id]
    if (!selectedOptionId) return

    setAttemptBusyId(item.id)
    setError('')
    try {
      const feedback = await submitQuizAttempt(
        userId,
        item.id,
        selectedOptionId,
        courseId,
      )
      setAttemptFeedback((current) => ({ ...current, [item.id]: feedback }))
      await onGenerated()
    } catch (attemptError) {
      setError(getErrorMessage(attemptError))
    } finally {
      setAttemptBusyId(null)
    }
  }

  async function handleRemoveItem(item: QuizItem) {
    const confirmed = window.confirm(
      'Remove this question from practice? Answered questions are archived so learning history is kept.',
    )
    if (!confirmed) return

    setRemovalBusyId(item.id)
    setError('')
    setRemovalMessage('')
    try {
      const result = await deleteQuizItem(userId, item.id, courseId)
      setGenerated((current) =>
        current.filter((quizItem) => quizItem.id !== result.item_id),
      )
      setSelectedOptions((current) => {
        const next = { ...current }
        delete next[result.item_id]
        return next
      })
      setAttemptFeedback((current) => {
        const next = { ...current }
        delete next[result.item_id]
        return next
      })
      setRemovalMessage(
        result.action === 'deleted'
          ? 'Question deleted.'
          : 'Question archived and removed from practice.',
      )
      await onGenerated()
    } catch (removeError) {
      setError(getErrorMessage(removeError))
    } finally {
      setRemovalBusyId(null)
    }
  }

  return (
    <div className="grid two">
      <section className="panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <ClipboardList size={18} aria-hidden="true" />
            Generate
          </h3>
          <span className="badge info">{materialCount} source files</span>
        </div>
        <div className="panel-body stack">
          <form className="stack" onSubmit={handleGenerate}>
            <label>
              <span className="field-label">Focus</span>
              <input
                className="input"
                onChange={(event) => setFocus(event.target.value)}
                placeholder="Whole course"
                value={focus}
              />
            </label>
            <div className="form-row">
              <label>
                <span className="field-label">Count</span>
                <input
                  className="input"
                  max={10}
                  min={1}
                  onChange={(event) => setCount(Number(event.target.value))}
                  type="number"
                  value={count}
                />
              </label>
              <label>
                <span className="field-label">Difficulty</span>
                <select
                  className="select"
                  onChange={(event) => setDifficulty(event.target.value)}
                  value={difficulty}
                >
                  <option value="easy">easy</option>
                  <option value="medium">medium</option>
                  <option value="hard">hard</option>
                </select>
              </label>
              <button className="button" disabled={busy || materialCount === 0} type="submit">
                {busy ? <Loader2 size={16} aria-hidden="true" /> : <CheckCircle2 size={16} />}
                Generate
              </button>
            </div>
          </form>
          {error && <div className="error">{error}</div>}
          {removalMessage && <div className="notice">{removalMessage}</div>}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <FileText size={18} aria-hidden="true" />
            Traceable Items
          </h3>
          <span className="badge info">{visibleItems.length} items</span>
        </div>
        <div className="panel-body">
          {visibleItems.length === 0 ? (
            <EmptyState label="No quiz items" />
          ) : (
            <div className="list">
              {visibleItems.map((item) => {
                const selectedOptionId = selectedOptions[item.id]
                const feedback = attemptFeedback[item.id]
                const hasOptions = item.options.length > 0
                return (
                  <div className="item-row quiz-card" key={item.id}>
                    <div className="item-topline">
                      <h4 className="item-title">{item.question}</h4>
                      <div className="item-actions">
                        <span className={`badge ${traceBadgeClass(item.traceability_label)}`}>
                          {item.traceability_label}
                        </span>
                        <button
                          aria-label="Remove quiz item"
                          className="icon-button danger"
                          disabled={removalBusyId === item.id}
                          onClick={() => void handleRemoveItem(item)}
                          title="Remove from practice"
                          type="button"
                        >
                          {removalBusyId === item.id ? (
                            <Loader2 size={15} aria-hidden="true" />
                          ) : (
                            <Trash2 size={15} aria-hidden="true" />
                          )}
                        </button>
                      </div>
                    </div>

                    {hasOptions ? (
                      <div className="option-list" role="group" aria-label="Answer options">
                        {item.options.map((option) => {
                          const isSelected = selectedOptionId === option.id
                          const isCorrect =
                            feedback && feedback.correct_option_id === option.id
                          const isIncorrectSelection =
                            feedback &&
                            feedback.selected_option_id === option.id &&
                            !feedback.is_correct
                          return (
                            <button
                              className={[
                                'option-button',
                                isSelected ? 'selected' : '',
                                isCorrect ? 'correct' : '',
                                isIncorrectSelection ? 'incorrect' : '',
                              ]
                                .filter(Boolean)
                                .join(' ')}
                              disabled={Boolean(feedback)}
                              key={option.id}
                              onClick={() =>
                                setSelectedOptions((current) => ({
                                  ...current,
                                  [item.id]: option.id,
                                }))
                              }
                              type="button"
                            >
                              <span className="option-letter">{option.id}</span>
                              <span>{option.text}</span>
                            </button>
                          )
                        })}
                      </div>
                    ) : (
                      <p className="answer">{item.answer}</p>
                    )}

                    {hasOptions && (
                      <div className="quiz-actions">
                        <button
                          className="button secondary"
                          disabled={
                            !selectedOptionId ||
                            Boolean(feedback) ||
                            attemptBusyId === item.id
                          }
                          onClick={() => void handleSubmitAttempt(item)}
                          type="button"
                        >
                          {attemptBusyId === item.id ? (
                            <Loader2 size={16} aria-hidden="true" />
                          ) : (
                            <CheckCircle2 size={16} aria-hidden="true" />
                          )}
                          {feedback ? 'Recorded' : 'Submit answer'}
                        </button>
                      </div>
                    )}

                    {feedback && (
                      <div
                        className={`attempt-feedback ${
                          feedback.is_correct ? 'correct' : 'incorrect'
                        }`}
                      >
                        <strong>{feedback.is_correct ? 'Correct' : 'Not quite'}</strong>
                        <span>
                          Correct answer: {feedback.correct_option_id}.{' '}
                          {feedback.correct_option_text}
                        </span>
                        <p>{feedback.explanation}</p>
                      </div>
                    )}

                    <div className="badge-row">
                      <span className="badge">{item.difficulty}</span>
                      <span className="badge">{item.question_type}</span>
                      {item.source_chunk_ids.map((id) => (
                        <span className="badge" key={id}>
                          chunk {id}
                        </span>
                      ))}
                    </div>
                    {item.evidence_quote && <p className="quote">{item.evidence_quote}</p>}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function ReviewView({
  courseId,
  dueReviews,
  learnerState,
  mastery,
  userId,
  onReviewed,
}: {
  courseId: number | null
  dueReviews: DueReviewItem[]
  learnerState: LearnerState | null
  mastery: MasteryResponse | null
  userId: string
  onReviewed: () => Promise<void>
}) {
  const [busyItemId, setBusyItemId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const summary = mastery?.summary
  const dueById = useMemo(
    () => new Set(dueReviews.map((review) => review.item.id)),
    [dueReviews],
  )

  async function handleReview(itemId: number, rating: number, isCorrect: boolean) {
    setBusyItemId(itemId)
    setError('')
    try {
      await submitReview(userId, itemId, rating, isCorrect, courseId)
      await onReviewed()
    } catch (reviewError) {
      setError(getErrorMessage(reviewError))
    } finally {
      setBusyItemId(null)
    }
  }

  return (
    <div className="grid">
      <div className="metric-strip">
        <Metric
          label="Learner state"
          value={`${Math.round((learnerState?.mastery_score ?? 0) * 100)}%`}
        />
        <Metric
          label="Recent accuracy"
          value={`${Math.round((learnerState?.recent_accuracy ?? 0) * 100)}%`}
        />
        <Metric label="Attempts" value={learnerState?.attempt_count ?? 0} />
        <Metric label="Errors" value={learnerState?.consecutive_errors ?? 0} />
      </div>
      <div className="metric-strip compact">
        <Metric label="Items" value={summary?.total_items ?? 0} />
        <Metric label="Reviewed" value={summary?.reviewed_items ?? 0} />
        <Metric label="Due" value={summary?.due_items ?? 0} />
        <Metric
          label="Review due"
          value={learnerState?.review_due ? 'yes' : 'no'}
        />
      </div>

      {error && <div className="error">{error}</div>}

      <div className="grid two">
        <section className="panel">
          <div className="panel-header">
            <h3 className="panel-title">
              <Brain size={18} aria-hidden="true" />
              Due Review
            </h3>
            <span className="badge info">{dueReviews.length} due</span>
          </div>
          <div className="panel-body">
            {dueReviews.length === 0 ? (
              <EmptyState label="No due items" />
            ) : (
              <div className="list">
                {dueReviews.map(({ item }) => (
                  <div className="item-row" key={item.id}>
                    <h4 className="item-title">{item.question}</h4>
                    <p className="answer">{item.answer}</p>
                    <div className="review-actions">
                      {[1, 2, 3, 4].map((rating) => (
                        <button
                          className={rating >= 3 ? 'button secondary' : 'button ghost'}
                          disabled={busyItemId === item.id}
                          key={rating}
                          onClick={() => handleReview(item.id, rating, rating >= 3)}
                          type="button"
                        >
                          {rating}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h3 className="panel-title">
              <BarChart3 size={18} aria-hidden="true" />
              Mastery
            </h3>
          </div>
          <div className="panel-body">
            {!mastery || mastery.items.length === 0 ? (
              <EmptyState label="No mastery data" />
            ) : (
              <div className="list">
                {mastery.items.map((item) => (
                  <div className="item-row compact" key={item.item_id}>
                    <div className="item-topline">
                      <h4 className="item-title">{item.question}</h4>
                      <span className={`badge ${dueById.has(item.item_id) ? 'warn' : 'good'}`}>
                        {item.is_due ? 'due' : 'scheduled'}
                      </span>
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{
                          width: `${Math.round(item.mastery_probability * 100)}%`,
                        }}
                      />
                    </div>
                    <div className="badge-row">
                      <span className="badge">
                        {Math.round(item.mastery_probability * 100)}%
                      </span>
                      <span className="badge">{item.review_count} reviews</span>
                      {item.latest_rating && (
                        <span className="badge">rating {item.latest_rating}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

function AnswerMetrics({ evaluation }: { evaluation: AnswerEvaluation }) {
  return (
    <div className="metric-strip">
      <Metric label="Groundedness" value={`${Math.round(evaluation.groundedness_score * 100)}%`} />
      <Metric label="Citation" value={formatEvaluationPercent(evaluation.citation_precision)} />
      <Metric label="Unsupported" value={`${Math.round(evaluation.unsupported_claim_rate * 100)}%`} />
      <Metric label="Claims" value={evaluation.claim_count} />
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <p className="metric-value">{value}</p>
      <p className="metric-label">{label}</p>
    </div>
  )
}

function EmptyState({ label }: { label: string }) {
  return <div className="empty">{label}</div>
}

function healthLabel(status: HealthStatus) {
  if (status === 'connected') return 'Backend connected'
  if (status === 'unreachable') return 'Backend unreachable'
  return 'Checking backend'
}

function statusDotClass(status: HealthStatus) {
  if (status === 'connected') return 'status-dot ok'
  if (status === 'unreachable') return 'status-dot bad'
  return 'status-dot'
}

function pageTitle(view: View) {
  const titles = {
    documents: 'Documents',
    tutor: 'Adaptive Tutor',
    chat: 'Evidence Chat',
    quiz: 'Quiz Lab',
    review: 'Review & Mastery',
    progress: 'Progress',
    evaluation: 'Evaluation',
  }
  return titles[view]
}

function pageKicker(view: View) {
  const subtitles = {
    documents: 'Course material ingestion and vector knowledge base',
    tutor: 'Policy-aware tutoring actions driven by evidence and learner state',
    chat: 'Claim-level evidence, citations and grounded comparison',
    quiz: 'Traceable practice items linked to source chunks',
    review: 'Due items, ratings and mastery indicators',
    progress: 'Estimated concept mastery, learning signals and guided activity',
    evaluation: 'Grounded vs ungrounded reliability experiments',
  }
  return subtitles[view]
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-IE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatNullablePercent(value: number | null) {
  return value == null ? 'Unobserved' : `${Math.round(value * 100)}%`
}

function formatEvaluationPercent(value: number | null) {
  return value == null ? 'N/A' : `${Math.round(value * 100)}%`
}

function formatProgressStatus(status: ProgressConceptStatus) {
  const labels = {
    unobserved: 'Unobserved',
    needs_attention: 'Needs attention',
    developing: 'Developing',
    strong: 'Strong',
  }
  return labels[status]
}

function progressStatusBadgeClass(status: ProgressConceptStatus) {
  if (status === 'strong') return 'good'
  if (status === 'developing' || status === 'unobserved') return 'info'
  return 'warn'
}

function formatAttentionReason(reason: string) {
  const labels: Record<string, string> = {
    review_due: 'Review due',
    needs_attention: 'Needs attention',
    consecutive_errors: 'Consecutive errors',
    low_estimated_mastery: 'Low estimated mastery',
    low_recent_accuracy: 'Low recent accuracy',
    recent_learning_signal: 'Recent learning signal',
  }
  return labels[reason] ?? reason.replace(/_/g, ' ')
}

function formatMisconceptionType(type: string) {
  const labels: Record<string, string> = {
    concept_confusion: 'Possible concept confusion',
    incorrect_definition: 'Possible definition issue',
    missing_prerequisite: 'Possible missing prerequisite',
    incomplete_reasoning: 'Possible reasoning gap',
    source_misinterpretation: 'Possible source misreading',
    unknown: 'Unclear learning signal',
  }
  return labels[type] ?? type.replace(/_/g, ' ')
}

function formatCompletionCheck(concept: CourseProgress['concepts'][number]) {
  const latest = concept.socratic_activity.latest_completion_correct
  if (latest == null) return 'None'
  return latest ? 'Correct' : 'Not quite'
}

function canStartSocraticSession(response: TutorResponse) {
  const evidenceStrength =
    response.decision.evidence_state_snapshot.evidence_strength
  return (
    response.decision.selected_action !== 'refuse' &&
    response.decision.concept_state_snapshot != null &&
    (evidenceStrength === 'high' || evidenceStrength === 'medium')
  )
}

function socraticLatestStorageKey(userId: string, courseId: number | null) {
  return `ai-tutor:socratic:latest:${userId}:${courseId ?? 'all'}`
}

function socraticDecisionStorageKey(
  userId: string,
  courseId: number | null,
  decisionId: number,
) {
  return `ai-tutor:socratic:${userId}:${courseId ?? 'all'}:${decisionId}`
}

function formatSocraticStage(stage: SocraticSession['current_stage']) {
  const labels = {
    diagnostic: 'Diagnostic',
    hint_1: 'Hint 1',
    hint_2: 'Hint 2',
    final_explanation: 'Final explanation',
    grounded_summary: 'Grounded summary',
  }
  return labels[stage]
}

function formatSocraticAssessment(assessment: NonNullable<SocraticSession['assessment']>) {
  const labels = {
    correct: 'Correct',
    partially_correct: 'Partially correct',
    incorrect: 'Not quite',
    off_topic: 'Off topic',
  }
  return labels[assessment]
}

function socraticProgressLabel(session: SocraticSession) {
  if (session.status === 'completed') {
    return `Completed after ${session.turn_count} of ${session.max_turns} attempts`
  }
  return `Attempt ${Math.min(session.turn_count + 1, session.max_turns)} of ${
    session.max_turns
  }`
}

function socraticStatusBadgeClass(status: SocraticSession['status']) {
  if (status === 'completed') return 'good'
  if (status === 'abandoned') return 'warn'
  return 'info'
}

function socraticAssessmentBadgeClass(
  assessment: NonNullable<SocraticSession['assessment']>,
) {
  if (assessment === 'correct') return 'good'
  if (assessment === 'partially_correct') return 'warn'
  return 'bad'
}

function supportBadgeClass(label: string) {
  if (label === 'fully_supported') return 'good'
  if (label === 'partially_supported') return 'warn'
  return 'bad'
}

function traceBadgeClass(label: string) {
  if (label === 'fully_traceable') return 'good'
  if (label === 'partially_traceable' || label === 'weakly_traceable') return 'warn'
  return 'bad'
}

function evidenceBadgeClass(label: string) {
  if (label === 'high') return 'good'
  if (label === 'medium' || label === 'not_required') return 'info'
  if (label === 'low') return 'warn'
  return 'bad'
}

function tutorStatusBadgeClass(label: string) {
  if (label === 'answered' || label === 'quiz_ready' || label === 'review_ready') {
    return 'good'
  }
  if (label === 'partially_answered' || label === 'needs_more_material') return 'warn'
  return 'bad'
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Unexpected error'
}

export default App

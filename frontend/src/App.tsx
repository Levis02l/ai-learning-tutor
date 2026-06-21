import {
  BarChart3,
  BookOpen,
  Brain,
  CheckCircle2,
  ClipboardList,
  FileText,
  FileUp,
  Gauge,
  Library,
  Loader2,
  MessageSquareText,
  RefreshCw,
  SearchCheck,
  Send,
  Upload,
} from 'lucide-react'
import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react'

import {
  chat,
  compareChat,
  evaluateAnswer,
  generateQuiz,
  getHealth,
  getMastery,
  listDocuments,
  listDueReviews,
  listQuizItems,
  submitReview,
  uploadDocument,
} from './api'
import type {
  AnswerEvaluation,
  ChatCompareResponse,
  ChatResponse,
  DocumentItem,
  DueReviewItem,
  MasteryResponse,
  QuizItem,
} from './types'

type View = 'documents' | 'chat' | 'quiz' | 'review'
type HealthStatus = 'checking' | 'connected' | 'unreachable'

const userIdDefault = 'demo-user'

function App() {
  const [activeView, setActiveView] = useState<View>('documents')
  const [userId, setUserId] = useState(userIdDefault)
  const [health, setHealth] = useState<HealthStatus>('checking')
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [quizItems, setQuizItems] = useState<QuizItem[]>([])
  const [dueReviews, setDueReviews] = useState<DueReviewItem[]>([])
  const [mastery, setMastery] = useState<MasteryResponse | null>(null)
  const [globalError, setGlobalError] = useState('')

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
      const [docs, quizzes, due, masterySnapshot] = await Promise.all([
        listDocuments(userId),
        listQuizItems(userId),
        listDueReviews(userId),
        getMastery(userId),
      ])
      setDocuments(docs)
      setQuizItems(quizzes)
      setDueReviews(due)
      setMastery(masterySnapshot)
    } catch (error) {
      setGlobalError(getErrorMessage(error))
    }
  }, [userId])

  useEffect(() => {
    void refreshHealth()
  }, [refreshHealth])

  useEffect(() => {
    void refreshCoreData()
  }, [refreshCoreData])

  const navItems = [
    { id: 'documents' as const, label: 'Documents', icon: Library },
    { id: 'chat' as const, label: 'Evidence Chat', icon: MessageSquareText },
    { id: 'quiz' as const, label: 'Quiz Lab', icon: ClipboardList },
    { id: 'review' as const, label: 'Review', icon: Brain },
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
            <button className="button secondary" onClick={refreshCoreData} type="button">
              <RefreshCw size={16} aria-hidden="true" />
              Refresh
            </button>
          </div>
        </header>

        {globalError && <div className="error">{globalError}</div>}

        {activeView === 'documents' && (
          <DocumentsView
            documents={documents}
            userId={userId}
            onUploaded={refreshCoreData}
          />
        )}
        {activeView === 'chat' && <ChatView userId={userId} />}
        {activeView === 'quiz' && (
          <QuizView
            items={quizItems}
            userId={userId}
            onGenerated={refreshCoreData}
          />
        )}
        {activeView === 'review' && (
          <ReviewView
            dueReviews={dueReviews}
            mastery={mastery}
            userId={userId}
            onReviewed={refreshCoreData}
          />
        )}
      </main>
    </div>
  )
}

function DocumentsView({
  documents,
  userId,
  onUploaded,
}: {
  documents: DocumentItem[]
  userId: string
  onUploaded: () => Promise<void>
}) {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function handleUpload(event: FormEvent) {
    event.preventDefault()
    if (!file) return

    setBusy(true)
    setError('')
    try {
      await uploadDocument(userId, file)
      setFile(null)
      await onUploaded()
    } catch (uploadError) {
      setError(getErrorMessage(uploadError))
    } finally {
      setBusy(false)
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
        </div>
        <div className="panel-body">
          <form className="stack" onSubmit={handleUpload}>
            <label className="file-input">
              <span className="field-label">Course material</span>
              <input
                accept=".pdf,.pptx,.docx,.txt,.md"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
            {error && <div className="error">{error}</div>}
            <button className="button" disabled={!file || busy} type="submit">
              {busy ? (
                <Loader2 className="spin" size={16} aria-hidden="true" />
              ) : (
                <Upload size={16} aria-hidden="true" />
              )}
              Upload
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
                    <span className={`badge ${document.status === 'done' ? 'good' : 'warn'}`}>
                      {document.status}
                    </span>
                  </div>
                  <div className="badge-row">
                    <span className="badge">{document.file_type}</span>
                    <span className="badge">{document.chunk_count} chunks</span>
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

function ChatView({ userId }: { userId: string }) {
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
        const result = await compareChat(userId, query, topK)
        setComparison(result)
        setEvaluation(await evaluateAnswer(result.grounded, true))
      } else {
        const result = await chat(userId, query, topK)
        setAnswer(result)
        setEvaluation(await evaluateAnswer(result, true))
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

function AnswerPanel({ title, response }: { title: string; response: ChatResponse }) {
  return (
    <div className="panel">
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
        {response && <span className="badge info">{response.sources.length} sources</span>}
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
  items,
  userId,
  onGenerated,
}: {
  items: QuizItem[]
  userId: string
  onGenerated: () => Promise<void>
}) {
  const [topic, setTopic] = useState('artificial intelligence')
  const [count, setCount] = useState(3)
  const [difficulty, setDifficulty] = useState('medium')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [generated, setGenerated] = useState<QuizItem[]>([])

  async function handleGenerate(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await generateQuiz(userId, topic, count, difficulty, 5)
      setGenerated(response.items)
      await onGenerated()
    } catch (quizError) {
      setError(getErrorMessage(quizError))
    } finally {
      setBusy(false)
    }
  }

  const visibleItems = generated.length > 0 ? generated : items

  return (
    <div className="grid two">
      <section className="panel">
        <div className="panel-header">
          <h3 className="panel-title">
            <ClipboardList size={18} aria-hidden="true" />
            Generate
          </h3>
        </div>
        <div className="panel-body stack">
          <form className="stack" onSubmit={handleGenerate}>
            <label>
              <span className="field-label">Topic</span>
              <input
                className="input"
                onChange={(event) => setTopic(event.target.value)}
                value={topic}
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
              <button className="button" disabled={busy || !topic.trim()} type="submit">
                {busy ? <Loader2 size={16} aria-hidden="true" /> : <CheckCircle2 size={16} />}
                Generate
              </button>
            </div>
          </form>
          {error && <div className="error">{error}</div>}
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
              {visibleItems.map((item) => (
                <div className="item-row" key={item.id}>
                  <div className="item-topline">
                    <h4 className="item-title">{item.question}</h4>
                    <span className={`badge ${traceBadgeClass(item.traceability_label)}`}>
                      {item.traceability_label}
                    </span>
                  </div>
                  <p className="answer">{item.answer}</p>
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
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function ReviewView({
  dueReviews,
  mastery,
  userId,
  onReviewed,
}: {
  dueReviews: DueReviewItem[]
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
      await submitReview(userId, itemId, rating, isCorrect)
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
        <Metric label="Items" value={summary?.total_items ?? 0} />
        <Metric label="Reviewed" value={summary?.reviewed_items ?? 0} />
        <Metric label="Due" value={summary?.due_items ?? 0} />
        <Metric
          label="Mastery"
          value={`${Math.round((summary?.average_mastery ?? 0) * 100)}%`}
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
      <Metric label="Citation" value={`${Math.round(evaluation.citation_precision * 100)}%`} />
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
    chat: 'Evidence Chat',
    quiz: 'Quiz Lab',
    review: 'Review & Mastery',
  }
  return titles[view]
}

function pageKicker(view: View) {
  const subtitles = {
    documents: 'Course material ingestion and vector knowledge base',
    chat: 'Claim-level evidence, citations and grounded comparison',
    quiz: 'Traceable practice items linked to source chunks',
    review: 'Due items, ratings and mastery indicators',
  }
  return subtitles[view]
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-IE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
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

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Unexpected error'
}

export default App

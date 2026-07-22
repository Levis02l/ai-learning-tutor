# V1-A Results and Discussion

## Results

### Overall reliability on answerable content

The paired formal evaluation contained 50 questions: 30 answerable, 10
partially answerable, and 10 unanswerable. Each question was answered under a
Grounded condition and an otherwise equivalent Ungrounded condition. The 40
answerable or partially answerable cases formed the factual-answer analysis.
Response-level claim rates macro-averaged the annotated substantive claims in
these 40 outputs per condition; refusal outputs were excluded. Refusal metrics
used the 10 unanswerable paired cases. Citation metrics used only the 40
applicable Grounded factual outputs because the Ungrounded baseline did not
produce source citations by design.

Within this frozen corpus and evaluation set, Grounding improved factual answer
quality. Mean human-rated correctness was
1.975 out of 2 for Grounded responses
and 1.625 for Ungrounded responses,
a paired difference of 0.350
(95% CI 0.200 to
0.500,
p < .001). The
fully correct rate was 97.5% under
Grounding and 65.0% without
Grounding, corresponding to a 32.5 percentage-point paired
difference
(p < .001).

The same pattern appeared in post-hoc course-evidence support. The mean rate of
fully course-supported claims was 98.5%
for Grounded responses and 83.5%
for Ungrounded responses, a 15.0 percentage-point
difference
(p < .001). The mean
unsupported-by-course claim rate was
0.0% for Grounded responses
and 7.6% for Ungrounded
responses (paired difference
-7.6
percentage points, p
= 0.031).

At claim level, 98.5% of the
132 Grounded substantive claims were fully
supported, compared with 86.8%
of 121 Ungrounded claims. No Grounded
substantive claim was annotated as unsupported or contradicted, whereas
6.6% of
Ungrounded claims fell into those categories.

### Differences by answerability

For the 30 fully answerable questions, Grounded responses achieved a mean
correctness score of
2.000, compared
with 1.733 for
Ungrounded responses. Both conditions had a 0% false-refusal rate on these
questions, showing that the reliability advantage did not result from refusing
questions that the course corpus could answer.

The difference was larger on the 10 partially answerable questions. Grounded
mean correctness was 1.900, compared
with 1.300 for Ungrounded responses
(p = 0.031). The
Grounded course-supported claim rate was
94.2%, compared with
46.7% without Grounding
(p = 0.016). Grounded
responses fully limited the unsupported portion in
80.0% of cases, compared with
60.0% for Ungrounded responses.
This difference was not statistically detectable in the small partial subset
(p = 0.500).

### Refusal behaviour

Grounding produced a marked difference on the 10 unanswerable questions. The
Grounded tutor correctly refused all 10 cases
(100.0%), whereas the Ungrounded condition
correctly refused 30.0%
(McNemar exact p = 0.016). No
Grounded response falsely answered an unanswerable question, while the
Ungrounded false-answer rate was 60.0%
(McNemar exact p
= 0.031).

### Citation traceability

Citation quality was evaluated only for Grounded factual responses because the
Ungrounded baseline was not designed to produce citations. Across the 40
answerable and partially answerable Grounded responses, mean citation precision
was 94.3%
and mean citation coverage was
96.2%.
Precision was lower for partially answerable questions
(84.2%)
than for fully answerable questions
(97.7%),
indicating that citation attribution became harder when a question extended
beyond what the source fully specified.

## Discussion

### Contribution of evidence grounding

Within the frozen course corpus and evaluation set, the results support the
claim that evidence-aware tutoring improved course-specific reliability and
traceability relative to the otherwise comparable Ungrounded baseline. The
Ungrounded model often answered general
conceptual questions correctly, but it was less reliable when a question
depended on a course-specific convention, experimental result, or explicit
scope limitation. Cases 020 and 022 illustrate this distinction: the
Ungrounded answers were plausible as general machine-learning explanations but
did not match the experiment or covariance convention used in the uploaded
notes. Grounding therefore contributed more than generic factual recall; it
aligned answers with the local instructional source.

The refusal results provide the clearest evidence of calibrated behaviour. A
general-purpose model may possess relevant world knowledge, but using that
knowledge violates the task when the tutor is expected to answer only from the
student's materials. The Grounded tutor refused every unanswerable case and
made no false answers, while the Ungrounded condition supplied unsupported
answers in six of ten cases. Case 048 also demonstrates that Grounding did not
create an artificial difference when both systems appropriately recognised
missing information: both conditions refused, and the recovered infrastructure
run retained explicit provenance.

### Grounding does not guarantee perfect interpretation

High course-support and citation scores should not be interpreted as proof that
every Grounded response was semantically perfect. Cases 034 and 040 expose two
important limitations. In case 034, the response extended a source statement
about a 50% breakdown point into an exact finite-sample outlier count. In case
040, the Grounded answer cited a reported R-squared value but incorrectly
described it as a test-set result. These failures show that a citation may be
topically relevant while the generated wording overstates what the evidence
entails. Claim-level review and citation precision are therefore both necessary;
the mere presence of a source marker is insufficient.

Partially answerable questions remain a further challenge. Grounding
substantially improved correctness and support for the answerable portion, but
the difference in fully limiting the unsupported portion was smaller and
uncertain. This suggests that retrieval and citation constraints help the tutor
identify usable evidence, while deciding exactly where to stop an answer still
requires careful uncertainty and refusal policies.

### Implications for trustworthy educational AI

For educational use, the practical value of Grounding is not that it makes an
LLM universally knowledgeable. Its value is that it constrains explanations to
the learner's course context, exposes the evidence behind substantive claims,
and improves refusal when the material is insufficient. This supports an
evidence-aware design in which answer correctness, post-hoc course support,
citation quality, and refusal behaviour are measured separately. In
particular, an Ungrounded answer without citations is not automatically wrong,
and a Grounded answer with citations is not automatically correct.

### Limitations

The evaluation used one uploaded course corpus, one configured language model,
and 50 paired questions. The answerable group was larger than the partial and
unanswerable groups, each of which contained only 10 cases. Confidence intervals
for those smaller groups are consequently wide. Inferential p-values were
treated as exploratory and were not adjusted for multiple comparisons; effect
sizes and confidence intervals should carry greater interpretive weight.

The final annotations were AI-assisted and received final author sign-off, but
the study did not include a second independent annotator. Inter-rater agreement
therefore cannot be reported. The paired design controls question difficulty
between conditions, but broader claims will require replication across courses,
document formats, subject areas, models, and independent evaluators. Finally,
the study evaluates response reliability rather than long-term learning gain;
the adaptive-policy and closed-loop evaluations address different parts of the
system and should be reported separately.

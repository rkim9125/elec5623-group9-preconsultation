import { translate } from "./i18n/core.js";

// Choice values are unchanged for compatibility with saved questionnaires.
// Only their labels are translated; free text never passes through this mapping.
const definition = {
  brand: "visit.notes",
  tagline: "your.story.ready.for.your.visit",
  stages: [
    "reason.for.visit",
    "your.symptoms",
    "related.information",
    "review.summary",
  ],
  start: "start.questionnaire",
  next: "continue",
  back: "back",
  editReturn: "save.and.return.to.summary",
  fields: {
    onset: {
      title: "when.did.your.symptoms.start",
      subtitle: "think.about.the.symptom.you.want.to.discuss.first",
      label: "when.symptoms.started",
      options: [
        {
          value: "오늘부터",
          labelKey: "today",
        },
        {
          value: "며칠 전부터",
          labelKey: "a.few.days.ago",
        },
        {
          value: "일주일 이상",
          labelKey: "at.least.a.week.ago",
        },
        {
          value: "한 달 이상",
          labelKey: "at.least.a.month.ago",
        },
      ],
      help: "noting.when.symptoms.started.can.help.you.explain.how.they.have.c",
    },
    course: {
      title: "how.have.your.symptoms.changed",
      subtitle: "compare.how.you.feel.now.with.when.they.started",
      label: "how.symptoms.have.changed",
      options: [
        {
          value: "비슷해요",
          labelKey: "about.the.same",
        },
        {
          value: "나아지고 있어요",
          labelKey: "getting.better",
        },
        {
          value: "더 불편해졌어요",
          labelKey: "getting.worse",
        },
        {
          value: "반복돼요",
          labelKey: "they.come.and.go",
        },
      ],
      help: "if.symptoms.come.and.go.we.ask.about.frequency.this.is.a.demo.que",
    },
    frequency: {
      title: "how.often.do.they.come.and.go",
      subtitle: "this.question.appears.because.you.selected.they.come.and.go",
      label: "how.often.symptoms.occur",
      options: [
        {
          value: "하루에 여러 번",
          labelKey: "several.times.a.day",
        },
        {
          value: "하루에 한 번 정도",
          labelKey: "about.once.a.day",
        },
        {
          value: "며칠에 한 번",
          labelKey: "every.few.days",
        },
        {
          value: "일정하지 않아요",
          labelKey: "no.regular.pattern",
        },
      ],
      help: "this.helps.you.describe.the.pattern.in.your.own.words",
    },
    severity: {
      title: "how.uncomfortable.do.you.feel",
      subtitle: "choose.the.answer.closest.to.how.you.feel.now",
      label: "current.discomfort",
      options: [
        {
          value: "가벼워요",
          labelKey: "mild",
        },
        {
          value: "보통이에요",
          labelKey: "moderate",
        },
        {
          value: "많이 불편해요",
          labelKey: "very.uncomfortable",
        },
      ],
      help: "this.records.how.you.feel.it.is.not.used.for.diagnosis.or.to.asse",
    },
    impact: {
      title: "how.is.this.affecting.daily.life",
      subtitle: "tell.us.how.it.affects.sleep.eating.work.or.movement",
      label: "impact.on.daily.life",
      options: [
        {
          value: "수면이 어려워요",
          labelKey: "difficulty.sleeping",
        },
        {
          value: "일·공부에 집중하기 어려워요",
          labelKey: "difficulty.concentrating.on.work.or.study",
        },
        {
          value: "움직이기 불편해요",
          labelKey: "difficulty.moving.around",
        },
      ],
      none: true,
      help: "note.the.everyday.difficulties.you.would.like.to.discuss.at.your",
    },
    history: {
      title: "is.there.any.medical.history.you.want.to.share",
      subtitle: "include.diagnosed.conditions.operations.or.treatments",
      label: "medical.history",
      placeholder:
        "for.example.i.have.been.treated.for.high.blood.pressure.for.three",
      none: true,
      help: "you.only.need.to.include.the.history.you.want.to.discuss.at.this",
    },
    questions: {
      title: "what.would.you.like.to.ask.the.doctor",
      subtitle: "note.any.concerns.or.questions.you.do.not.want.to.forget",
      label: "concerns.and.questions",
      placeholder:
        "for.example.is.there.anything.i.should.be.careful.about.in.daily",
      none: true,
      help: "record.the.questions.you.want.to.discuss.in.your.own.words",
    },
  },
};
function localize(value, locale) {
  if (Array.isArray(value)) return value.map((v) => localize(v, locale));
  if (value && typeof value === "object") {
    if (value.labelKey)
      return { value: value.value, label: translate(locale, value.labelKey) };
    return Object.fromEntries(
      Object.entries(value).map(([k, v]) => [k, localize(v, locale)]),
    );
  }
  return typeof value === "string" ? translate(locale, value) : value;
}
export const getCopy = (locale) => localize(definition, locale);
export function optionLabel(value, locale) {
  const option = Object.values(definition.fields)
    .flatMap((f) => f.options || [])
    .find((o) => o.value === value);
  return option ? translate(locale, option.labelKey) : value;
}

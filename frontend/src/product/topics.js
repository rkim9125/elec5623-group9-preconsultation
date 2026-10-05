const descriptions = {
  "WF-01": "Where it hurts, what it feels like, and how it affects your day.",
  "WF-02": "The pattern of your back discomfort and changes you have noticed.",
  "WF-03": "Neck or shoulder symptoms, movement and everyday activities.",
  "WF-04": "Hand, wrist or arm symptoms and their effect on daily tasks.",
  "WF-05":
    "Your headache pattern, associated experiences and appointment questions.",
  "WF-06": "Describe recurring dizziness for a planned consultation.",
  "WF-07": "Your energy levels, daily routine and how tiredness affects you.",
  "WF-08": "Your sleep routine, difficulties and how you feel during the day.",
  "WF-09": "Your cough pattern, changes and related symptoms you have noticed.",
  "WF-10": "Nasal symptoms and any allergy concerns you want to discuss.",
  "WF-11": "Throat symptoms, changes in your voice and their daily impact.",
  "WF-12": "Ear discomfort, hearing changes and your main concerns.",
  "WF-13": "Eye irritation or dryness and what you have noticed.",
  "WF-14": "Your abdominal discomfort, its pattern and effects on daily life.",
  "WF-15": "Heartburn or indigestion symptoms and questions for your doctor.",
  "WF-16": "Changes in bowel habits and details you feel comfortable sharing.",
  "WF-17": "The pattern of loose stools and related changes you have noticed.",
  "WF-18":
    "Urinary or bladder-control symptoms and your consultation priorities.",
  "WF-19":
    "Period-related questions, with your permission before sensitive details.",
  "WF-20":
    "Where the skin problem is, what it looks like and how it has changed.",
  "WF-21":
    "Your skin concerns, current treatment and progress you want to review.",
  "WF-22":
    "Your experiences of stress or anxiety and the support you want to discuss.",
  "WF-23": "How you have been feeling and what matters for your follow-up.",
  "WF-24":
    "Prepare your reported readings, current medicines and review questions.",
  "WF-25":
    "Organise your reported diabetes information for an existing-care review.",
  "WF-26": "Your reported asthma symptoms, current care and review priorities.",
  "WF-27": "The medicines you take and questions about your prescriptions.",
  "WF-28": "Which results you want to discuss and questions for the clinician.",
  "WF-29": "Your prevention or screening priorities for a planned discussion.",
  "WF-30":
    "Bring several concerns together and identify your appointment priorities.",
};
export const topicDescription = (topic) =>
  descriptions[topic.id] ||
  "Describe your concern and the questions you would like to discuss.";

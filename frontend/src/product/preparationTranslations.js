export const preparationTranslationRows = `
Anything else you would like your doctor to know?|还有什么希望医生了解的？|還有什麼希望醫生了解的？|의사에게 더 알리고 싶은 내용이 있나요?|ほかに医師に伝えておきたいことはありますか？
Anything else for your doctor|给医生的其他补充|給醫生的其他補充|의사에게 전할 추가 내용|医師への追加情報
What would you like to discuss about this topic?|这次就诊，您想具体讨论这方面的什么问题？|這次就診，您想具體討論這方面的什麼問題？|이번 진료에서 이 주제에 관해 어떤 내용을 이야기하고 싶나요?|今回の受診では、この件についてどんなことを相談したいですか？
A sentence or two is enough. We will guide you through the details next.|简单说一两句就好，接下来会逐步询问具体情况。|簡單說一兩句就好，接下來會逐步詢問具體情況。|한두 문장이면 충분해요. 다음 단계에서 자세히 물어볼게요.|一、二文で大丈夫です。詳しいことは次のステップで伺います。
What symptoms or changes have you noticed?|这次哪里不舒服，或出现了什么变化？|這次哪裡不舒服，或出現了什麼變化？|어디가 불편하거나 어떤 변화가 있었나요?|どこがつらいですか？どんな変化がありましたか？
Briefly describe where you feel it and what it feels like. We will ask about timing and daily activities next.|简单描述不舒服的部位和感觉。何时出现、如何影响生活，会在后面逐步询问。|簡單描述不舒服的部位和感覺。何時出現、如何影響生活，會在後面逐步詢問。|불편한 부위와 느낌을 간단히 적어 주세요. 시작 시점과 일상에 미치는 영향은 다음에 물어볼게요.|場所と感じ方を簡単に教えてください。いつからか、生活への影響は次に伺います。
Please briefly describe your leg discomfort.|请简单说说您的腿哪里不舒服、是什么感觉。|請簡單說說您的腿哪裡不舒服、是什麼感覺。|다리의 어느 부위가 어떻게 불편한지 간단히 알려 주세요.|脚のどこが、どのようにつらいか簡単に教えてください。
For example: My left calf aches when I walk. A sentence or two is enough.|例如：“走路时左边小腿酸痛。”简单说一两句就好。|例如：「走路時左邊小腿痠痛。」簡單說一兩句就好。|예: “걸을 때 왼쪽 종아리가 아파요.” 한두 문장이면 충분해요.|例：「歩くと左のふくらはぎが痛いです。」一、二文で大丈夫です。
Add any worries, questions for your doctor, or background that is not already in your profile. You can leave this blank.|可补充担忧、想问医生的问题，或档案里没有的病史。不需要重复已填写的信息，也可以留空。|可補充擔憂、想問醫生的問題，或檔案裡沒有的病史。不需要重複已填寫的資訊，也可以留空。|걱정되는 점, 의사에게 물을 질문, 프로필에 없는 병력을 적어 주세요. 이미 적은 내용은 반복하지 않아도 되며 비워 두셔도 돼요.|心配なこと、医師への質問、プロフィールにない病歴などを追加できます。記入済みの内容は繰り返さず、空欄でも構いません。
Tell us in your own words. You can type or use your voice.|用自己的话说就好，可以打字或使用语音。|用自己的話說就好，可以打字或使用語音。|직접 입력하거나 음성으로 편하게 알려 주세요.|ご自身の言葉で、文字か音声で伝えてください。
Saved details|已保存的信息|已儲存的資訊|저장된 정보|保存済みの情報
Your previous answer|上次的回答|上次的回答|이전 답변|前回の回答
Check whether this is still accurate for this visit. Nothing is filled in until you choose it.|请确认这次是否仍然适用。只有点击后才会填入本次回答。|請確認這次是否仍然適用。只有點擊後才會填入本次回答。|이번 진료에도 맞는 내용인지 확인하세요. 선택해야 이번 답변에 입력됩니다.|今回も正しい内容か確認してください。選択してから今回の回答に入力されます。
Use this answer for this visit|填入本次回答|填入本次回答|이번 답변에 사용|今回の回答に使う
Already recorded — no need to repeat|已记录的信息，无需重复填写|已記錄的資訊，無需重複填寫|이미 기록된 내용 — 반복하지 않아도 돼요|記録済みの情報 — 再入力は不要です
`.trim().split("\n").map((line) => line.split("|"));

# SECOND BRAIN / INTELLIGENT CRM

**Purpose.** This document captures the product direction, tasks, integrations, responsibilities and open questions discussed during our call. It intentionally separates what we want to build for the hackathon from what we want to explore and build afterwards.

**Core problem discussed.** I have many conversations, contacts, meetings, emails, screenshots, documents and follow-ups across different platforms. I do not always remember the status of each relationship, what was discussed, what I promised, who can help with a specific problem, or when I should contact someone again. The idea is to build a system that remembers this context and makes it useful.

**Core product idea discussed.** A second brain / intelligent CRM that collects relationship context, connects information about people and organisations, and allows the user to ask questions about their own network.

# **ROADMAP 1 \- HACKATHON=**

| Item | Working definition |
| :---- | :---- |
| Problem | Relationship information is fragmented across email, meetings, calendar, LinkedIn, messaging apps, screenshots, documents and human memory. |
| Product | A second-brain / intelligent CRM that connects context around people and organisations and lets the user interrogate their own network. |
| Core value | The system should help the user remember who someone is, how they know them, what happened, what is pending and why that person may matter now. |
| Hackathon objective | Build a working skeleton and at least one real end-to-end pipeline that can be reused after the event. |

# **\=**

## **1\. Goal for the hackathon**

Build a working skeleton of the second-brain CRM that can be demonstrated clearly during the hackathon and can later be reused as the base of a real product.

* The hackathon version does not need to include every possible feature or communication channel.  
* The priority is to make the main idea work properly and demonstrate a real pipeline.  
* The core should be reusable after the hackathon rather than becoming a one-off prototype.  
* We want to use the hackathon sponsor technologies strategically and implement them properly rather than adding many tools superficially.

## **2\. Main use case to demonstrate**

The demo should show that the system can understand who a person is, what history exists with that person, and how that relationship may be useful now.

* Example discussed: Sergey should have a profile connected to previous conversations, possible business discussions, the hackathon conversation, the NDA and other relevant context.  
* The system should know that different pieces of information belong to the same Sergey, rather than treating every email, screenshot or meeting as unrelated data.  
* The user should be able to ask questions such as: 'Who could introduce me to Web3 investors?'  
* Another key example discussed: 'I am in Dubai and I need to find a job. Who in my network could help me, which companies may be hiring, and who should I speak to?'  
* The answer should use the user's own relationship history: where someone was met, who introduced them, what was discussed and why reconnecting may make sense.

## **3\. Information the system should be able to collect**

The following sources and data types were discussed:

* Email, including Gmail and Outlook.  
* Multiple Gmail/email accounts. A specific pain point discussed was the need to connect several accounts rather than only one.  
* Calendar and meetings.  
* Collabute for meeting context, summaries and follow-ups.  
* LinkedIn contacts and relationship information.  
* WhatsApp.  
* Telegram.  
* X.  
* Screenshots sent by the user.  
* Documents, including documents such as an NDA connected to the relevant person's profile.  
* Contact information and organisations.

Other channels were mentioned during the brainstorming, including Instagram-style messaging automation and Snapchat. They were discussed as possible future integrations, not as required hackathon scope.

## **4\. LinkedIn constraint discussed**

* LinkedIn is important but technically sensitive because automation and scraping can create account-risk or platform-policy problems.  
* The current workaround discussed was downloading LinkedIn data periodically and importing it, although this is not ideal for a normal user.  
* A fake / non-primary LinkedIn profile may be available for the hackathon demo if needed.  
* The team needs to decide what LinkedIn connection is safe and realistic for the demo.

## **5\. Relationship memory and graph**

A major technical direction discussed was to move beyond isolated contact records and connect information through RAG / graph-style relationships.

* Create connected data for each person rather than only a flat CRM record.  
* Connect a person to their company, role, meetings, previous conversations and relationship with the user.  
* Use available email signatures and other sources to identify people and organisations.  
* Example discussed: Marta works at a real-estate company, was met two years ago, is Head of Sales, and may be relevant now because of a current job or business need.  
* The system should be able to compare the user's objective with the network and recommend who may be worth contacting.

## **6\. Follow-ups and reminders**

* The CRM should keep track of follow-ups.  
* The user should be able to indicate that they want to talk to a person again.  
* The system should know when a relationship has not been active for a period of time and surface it again.  
* The original second-brain example discussed: if Sergey shares an important personal update, or Daniel shares a work problem, the system should remember the context and later bring it back when relevant.  
* Example: if a relevant job appears in the user's network for Daniel, the system could connect that new information with the previous conversation.

## **7\. Collabute integration for the hackathon**

We discussed using Collabute specifically because it is one of the hackathon technologies and because meetings are directly relevant to the CRM.

* Use Collabute instead of, or alongside the concept of, a separate meeting-notes tool such as Granola.  
* Connect meetings from the CRM/calendar to Collabute.  
* After a meeting, bring the meeting outcome/context back into the CRM.  
* Use meeting information to support follow-ups with attendees.  
* This integration is strategically useful for the hackathon even if Collabute is not necessarily required in the final commercial product.

## **8\. Devin, Convex and Context.dev**

Both were identified as hackathon technologies we should try to use.

## **9\. Technical checklist Sergey said he needs**

1. Define which connections/integrations are required for the demo.  
- Main core   
- Collabute

2. Define what needs to be connected to the main platform.

3. Define the two demo pipelines he mentioned for registration / demonstration.

4. Define the core architecture and database approach.

5. Define what can be built directly by Sergey.

6. Define what Silvia can support with.

7. Identify whether a third technical person is necessary.

8. Prepare the system early enough to test bugs and features before the final presentation.

## **11\. Team responsibilities discussed**

| Silvia | Sergey |
| :---- | :---- |
| Prepare the presentation and overall storytelling. | Build the main technical core / brain of the product. |
| Prepare the demo pipeline and realistic data/use cases. | Define the technical architecture and required integrations. |
| Find people to test the product and identify bugs/features.\*after the hackthon | Implement integrations where possible. |
| Support technical tasks when Sergey provides a clear checklist of what is needed. | Tell Silvia exactly what help, data, integrations or people are needed. |
| Prepare a more visual / distinctive presentation or video concept so the demo is not just a boring CRM walkthrough. | Prepare a reliable working pipeline that can be shown live or in a video. |
|  |  |

## **13\. Demo and presentation approach (Silvia)**

* Do not present it as a standard CRM feature-by-feature walkthrough.  
* Create something more visual and memorable for the presentation, potentially including video.  
* The presentation can use a fictional person / character who has multiple startups, runs a marketing business, travels, meets many people and cannot remember everything.  
* The story should show the real problem: too many emails, meetings, contacts and information sources, with no single place that understands the full context.  
* Show the real working pipeline on screen.  
* Use a realistic contact/network scenario rather than only static mock-ups.

## **15\. Hackathon outcome we want**

* A working main core.  
* At least one real pipeline that can be demonstrated.  
* Useful integrations rather than superficial sponsor usage.  
* Enough stability for testing and presentation.  
* A skeleton that can be continued after the hackathon.

# **ROADMAP 2 \- AFTER THE HACKATHON**

## **1\. Main objective after the hackathon**

Continue from the same core and turn it into a useful product that can organise a person's relationships and information across multiple channels.

* Do not rebuild from zero after the hackathon.  
* Use the hackathon version as the main skeleton.  
* Add the commercial and operational features that were intentionally left out of the hackathon version.  
* Start testing whether people will actually pay for the product.

## **2\. Expand the integrations**

The longer-term product direction discussed includes connecting more of the user's real communication channels:

* Multiple Gmail accounts.  
* Outlook.  
* WhatsApp.  
* Telegram.  
* LinkedIn.  
* X.  
* Calendar and meetings.  
* Screenshots and documents.

Instagram-style messaging/automation and Snapchat were also mentioned as things worth exploring later, especially for marketing or sales use cases.

## **3\. Make the CRM understand the full relationship**

* Know who the person is across different sources.  
* Remember how and where the user met the person.  
* Remember previous conversations and business discussions.  
* Connect relevant documents such as NDAs to the person's profile.  
* Know the person's company and role where this information is available.  
* Remember relevant personal context mentioned in conversation.  
* Know when the user last spoke to the person.  
* Know whether the relationship is active or has gone cold.

## **4\. Make the system useful without perfect memory from the user**

A central requirement discussed is that the user should not need to remember the person's name, event or exact history before asking for help.

* Example: the user remembers that someone may be useful for a job or business opportunity but cannot remember exactly who introduced them or where they met.  
* The system should reconstruct the relationship from the stored data and surface the relevant person.

## **5\. Network-based search and recommendations**

The product should support questions such as:

* Who in my network can introduce me to Web3 investors?  
* Who in my network can help me find a job in Dubai?  
* Which companies I know may be hiring or may be interested in someone with my profile?  
* Which person should I talk to inside a company?  
* Which contacts have I not spoken to for a long time?  
* Who in my existing network can I pitch for my marketing / crypto services?

## **6\. Connect the user's network with new external opportunities**

* After checking the existing network, the system could also find new relevant companies or opportunities and add them to the CRM.  
* Example discussed: train the system on the type of crypto companies the user wants to work with, check who already exists in the network, evaluate the relationship, and identify who can be pitched.  
* Once the user's own network has been explored, the system can help discover new companies outside the existing network.  
* Example discussed: if a contact has a work problem and a relevant opportunity later appears, connect the two pieces of information.

## **7\. Follow-up intelligence**

* Remind the user when they wanted to reconnect with someone.  
* Surface people who have not been contacted for a defined period.  
* Keep track of pending follow-ups.  
* Use meeting and communication history to prepare the next contact.  
* Help the user avoid losing opportunities simply because they forgot a conversation or commitment.

## **8\. Meeting intelligence**

* Continue integrating meeting context into the person's CRM profile.  
* Use Collabute or the most suitable meeting tool to capture what happened in meetings.  
* Connect meeting outcomes to follow-ups and future conversations.  
* Collabute may be kept or removed later depending on whether it remains useful outside the hackathon; this was explicitly discussed as an open commercial/product decision.

## **9\. Product research and benchmarking**

Silvia has already been looking at other relationship-management / productivity products and comparing what exists.

* Continue reviewing comparable products and identify what they do well and what they do not solve.  
* The call referenced an existing relationship-management product as a benchmark and discussed the idea of starting from a familiar relationship-management experience and improving it with AI.  
* The key observation from the discussion was that several tools solve parts of the problem, but Silvia has not found one that solves the complete problem the way she wants.

## **10\. Commercial validation**

After the hackathon, Silvia's role would include taking the product to potential users and understanding whether there is a real market.

9. Show the product to people who have this problem.  
10. Use LinkedIn and Silvia's network to test interest if the product is good enough.  
11. Visit or speak with potential users/companies and show them a demo.  
12. Understand which type of person is most interested in the product.  
13. Ask how much they would be willing to pay.  
14. Use that feedback to decide which features and integrations to build next.

## **11\. Pricing discussion**

Pricing was discussed, but no final price was agreed.

* Sergey suggested USD 99 per year.  
* Silvia considered that too cheap.  
* Silvia said that if the tool truly solved this problem for her, she could imagine paying around USD 50-100, reflecting the value of having her life and relationships organised.  
* The correct pricing therefore needs to be validated with real users after the hackathon.

## **12\. Funding and infrastructure**

* The product should not require external investment just to start testing the idea.  
* Some models / APIs / inference may still create technical costs.  
* If the demo is strong, the team can apply for credits or support after the hackathon to continue development.  
* Proceed step by step rather than trying to finance or build everything immediately.

## **13\. Technical direction after the hackathon**

* Keep building the graph / RAG-based relationship memory discussed during the call.  
* Improve identity matching between people, companies, emails and conversations.  
* Improve the quality of network search and recommendations.  
* Add integrations progressively rather than all at once.  
* Test continuously for bugs and missing features.  
* Keep the technical core flexible enough to connect new channels later.

## **14\. Roles after the hackathon**

**Silvia:** Product direction, user problem, user testing, demos, presentation, commercial validation, reaching potential users, understanding willingness to pay, and deciding which use cases are most valuable.

**Sergey:** Technical core, architecture, integrations, implementation and technical feasibility.

**Shared:** Decide what to build next based on what works technically and what users actually want.

## **15\. Open questions carried forward from the call**

* Which integrations are essential for the first working version?  
* How exactly should Context.dev be used?  
* How exactly should Convex be used?  
* What is the safest and most practical LinkedIn integration approach?  
* Do we need a third technical contributor for integrations?  
* Which communication channels should be prioritised after the hackathon?  
* Which user segment is willing to pay the most for this problem?  
* What price are users actually willing to pay?  
* Should Collabute remain part of the commercial product or mainly serve the hackathon integration?

## **16\. Immediate next actions from the call**

15. Silvia prepares these two roadmaps: hackathon and post-hackathon.  
16. Sergey prepares the technical needs/checklist and thinks through the technical implementation day by day.  
17. Sergey defines what he can do directly and what he needs help with.  
18. Silvia supports the missing tasks and looks for another technical person only if required.  
19. Prepare the demo pipeline as early as possible.  
20. Prepare testing for bugs and features.  
21. Prepare a more visual presentation/video approach in parallel with development.

# **Working principle**

**Build the core first. Use the hackathon to prove it works. Then use real users to decide what the final product should become.**
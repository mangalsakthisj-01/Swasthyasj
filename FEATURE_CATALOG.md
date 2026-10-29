# SwasthyaGrid Feature Inventory

This inventory distinguishes features present in this quick-deploy prototype from ideas requiring additional implementation/integrations. It is not a claim that every roadmap item is already implemented.

## Latest additions in this build (implemented and smoke-tested)

- Admin creates and publishes hotspot advisories by ward or All Areas, with severity, category, public details, precautions, source, optional coordinates, and expiry.
- Publishing creates persistent in-app notifications for matching active Citizen accounts.
- Closing a published advisory requires a reason, creates an audit event, and queues closure-update notifications for citizens in scope.
- Citizens have a notification inbox with unread/read state and download their own case PDF plus personal case-history CSV.
- Complaint assignment and operational status changes notify the citizen in-app. Citizen reopen events notify the responsible operational roles.
- Field Officer structured investigation form records visit time, inspection outcome, location confirmation, observations, findings, severity assessment, people potentially affected, environment, safety action, work performed, materials, department referral, blockers, recommendation, contact/feedback, follow-up, conclusion, and notes.
- Investigation reports are stored persistently with unique report IDs, validated backend permissions, and PDF export.
- Admin and permitted Representative views can review/download investigation reports; officers can download PDFs and their investigation index.
- PDF export uses escaped user-supplied text and includes a safety limitation note.

## Present in this ZIP (prototype scope)
1. Four role dashboards (Citizen, Field Officer, Admin, Representative) — included in the current code, subject to prototype limitations.
2. Password hashing for demo account credentials — included in the current code, subject to prototype limitations.
3. Backend role checks for case visibility — included in the current code, subject to prototype limitations.
4. Citizen complaint creation — included in the current code, subject to prototype limitations.
5. Unique complaint tracking IDs — included in the current code, subject to prototype limitations.
6. Complaint category selection — included in the current code, subject to prototype limitations.
7. Severity selection — included in the current code, subject to prototype limitations.
8. Critical safety keyword override — included in the current code, subject to prototype limitations.
9. Rule-based triage fallback — included in the current code, subject to prototype limitations.
10. Optional Gemini vision/text review — included in the current code, subject to prototype limitations.
11. Explicit consent for external AI review — included in the current code, subject to prototype limitations.
12. AI uncertainty routes to human review — included in the current code, subject to prototype limitations.
13. Image/audio/video/PDF evidence attachments — included in the current code, subject to prototype limitations.
14. Per-file upload size checks — included in the current code, subject to prototype limitations.
15. Evidence download for authorised viewers — included in the current code, subject to prototype limitations.
16. Officer remarks — included in the current code, subject to prototype limitations.
17. Action-taken recording — included in the current code, subject to prototype limitations.
18. Status update workflow — included in the current code, subject to prototype limitations.
19. Citizen case history — included in the current code, subject to prototype limitations.
20. Citizen reopen request for resolved cases — included in the current code, subject to prototype limitations.
21. Field Officer case queue — included in the current code, subject to prototype limitations.
22. Officer jurisdiction filtering — included in the current code, subject to prototype limitations.
23. Admin user creation — included in the current code, subject to prototype limitations.
24. Role assignment during account creation — included in the current code, subject to prototype limitations.
25. Jurisdiction assignment — included in the current code, subject to prototype limitations.
26. Complaint assignment to officers — included in the current code, subject to prototype limitations.
27. Representative assignment — included in the current code, subject to prototype limitations.
28. Representative oversight view — included in the current code, subject to prototype limitations.
29. Representative guidance notes — included in the current code, subject to prototype limitations.
30. Critical complaint escalation — included in the current code, subject to prototype limitations.
31. Audit log for login and workflow actions — included in the current code, subject to prototype limitations.
32. CSV report export — included in the current code, subject to prototype limitations.
33. Dashboard KPI cards — included in the current code, subject to prototype limitations.
34. Status distribution chart — included in the current code, subject to prototype limitations.
35. Map pin input for reports — included in the current code, subject to prototype limitations.
36. Latitude validation — included in the current code, subject to prototype limitations.
37. Longitude validation — included in the current code, subject to prototype limitations.
38. Incident map for reports with coordinates — included in the current code, subject to prototype limitations.
39. Area/category hotspot grouping — included in the current code, subject to prototype limitations.
40. Minimum three-report hotspot threshold — included in the current code, subject to prototype limitations.
41. Approximate public hotspot coordinates — included in the current code, subject to prototype limitations.
42. Hotspot verification label — included in the current code, subject to prototype limitations.
43. Map freshness/limitations copy — included in the current code, subject to prototype limitations.
44. Map coordinate table view — included in the current code, subject to prototype limitations.
45. Case filtering through role-visible data — included in the current code, subject to prototype limitations.
46. Persistent SQLite case storage — included in the current code, subject to prototype limitations.
47. Persistent evidence BLOB storage — included in the current code, subject to prototype limitations.
48. Password minimum length enforcement — included in the current code, subject to prototype limitations.
49. User active status check — included in the current code, subject to prototype limitations.
50. Safe fallback if AI is unavailable — included in the current code, subject to prototype limitations.

## Additional innovation roadmap (not all implemented yet)
1. Tamil/English voice-to-text intake — planned/needs implementation, configuration, or validation.
2. Tamil/English interface toggle — planned/needs implementation, configuration, or validation.
3. Browser GPS capture with explicit consent — planned/needs implementation, configuration, or validation.
4. Ward boundary GIS layers — planned/needs implementation, configuration, or validation.
5. PostGIS geospatial query backend — planned/needs implementation, configuration, or validation.
6. Map time slider — planned/needs implementation, configuration, or validation.
7. Hotspot trend by rolling time windows — planned/needs implementation, configuration, or validation.
8. Weather integration with source timestamps — planned/needs implementation, configuration, or validation.
9. Official health advisory approval workflow — planned/needs implementation, configuration, or validation.
10. SMS notification provider integration — planned/needs implementation, configuration, or validation.
11. Email notification integration — planned/needs implementation, configuration, or validation.
12. Push notification integration — planned/needs implementation, configuration, or validation.
13. Notification preferences — planned/needs implementation, configuration, or validation.
14. Notification delivery retries — planned/needs implementation, configuration, or validation.
15. SLA deadline configuration — planned/needs implementation, configuration, or validation.
16. SLA pre-breach reminders — planned/needs implementation, configuration, or validation.
17. Automatic overdue escalation job — planned/needs implementation, configuration, or validation.
18. Incident duplicate suggestion — planned/needs implementation, configuration, or validation.
19. Parent incident with child complaint IDs — planned/needs implementation, configuration, or validation.
20. Independent corroboration weighting — planned/needs implementation, configuration, or validation.
21. Before/after resolution evidence packet — planned/needs implementation, configuration, or validation.
22. Evidence file hashing — planned/needs implementation, configuration, or validation.
23. Citizen resolution confirmation — planned/needs implementation, configuration, or validation.
24. Citizen satisfaction survey — planned/needs implementation, configuration, or validation.
25. Reopen reason taxonomy — planned/needs implementation, configuration, or validation.
26. Offline field draft queue — planned/needs implementation, configuration, or validation.
27. Offline sync conflict resolution — planned/needs implementation, configuration, or validation.
28. PWA install support — planned/needs implementation, configuration, or validation.
29. Smart dispatch by distance — planned/needs implementation, configuration, or validation.
30. Workload balancing — planned/needs implementation, configuration, or validation.
31. Skill/equipment-based assignment — planned/needs implementation, configuration, or validation.
32. Cross-department dependency graph — planned/needs implementation, configuration, or validation.
33. Department blocker tracking — planned/needs implementation, configuration, or validation.
34. Resource requirement estimation — planned/needs implementation, configuration, or validation.
35. Civic Action Planner — planned/needs implementation, configuration, or validation.
36. Ward campaign tracking — planned/needs implementation, configuration, or validation.
37. Public accountability scorecard — planned/needs implementation, configuration, or validation.
38. Small-count privacy suppression — planned/needs implementation, configuration, or validation.
39. Public map spatial aggregation — planned/needs implementation, configuration, or validation.
40. Report retention policy UI — planned/needs implementation, configuration, or validation.
41. Data export approval flow — planned/needs implementation, configuration, or validation.
42. Admin audit search filters — planned/needs implementation, configuration, or validation.
43. Immutable external audit sink — planned/needs implementation, configuration, or validation.
44. Password reset workflow — planned/needs implementation, configuration, or validation.
45. Invitation-based account provisioning — planned/needs implementation, configuration, or validation.
46. MFA for staff roles — planned/needs implementation, configuration, or validation.
47. Rate limiting — planned/needs implementation, configuration, or validation.
48. CSRF/session hardening review — planned/needs implementation, configuration, or validation.
49. Secure private object storage — planned/needs implementation, configuration, or validation.
50. Managed PostgreSQL migration — planned/needs implementation, configuration, or validation.
51. Automated database backups — planned/needs implementation, configuration, or validation.
52. Backup restore drill — planned/needs implementation, configuration, or validation.
53. Database migration versioning — planned/needs implementation, configuration, or validation.
54. Virus scanning for uploads — planned/needs implementation, configuration, or validation.
55. Video key-frame extraction — planned/needs implementation, configuration, or validation.
56. Audio transcription pipeline — planned/needs implementation, configuration, or validation.
57. Image quality assessment — planned/needs implementation, configuration, or validation.
58. Image metadata review — planned/needs implementation, configuration, or validation.
59. Duplicate image perceptual hashing — planned/needs implementation, configuration, or validation.
60. Visual category classifier evaluation — planned/needs implementation, configuration, or validation.
61. AI model version tracking — planned/needs implementation, configuration, or validation.
62. AI reviewer override reason — planned/needs implementation, configuration, or validation.
63. Model confidence calibration — planned/needs implementation, configuration, or validation.
64. False-negative monitoring — planned/needs implementation, configuration, or validation.
65. Bias evaluation across categories — planned/needs implementation, configuration, or validation.
66. AI service health panel — planned/needs implementation, configuration, or validation.
67. Map tile/source attribution — planned/needs implementation, configuration, or validation.
68. Map layer toggles — planned/needs implementation, configuration, or validation.
69. Heatmap overlay — planned/needs implementation, configuration, or validation.
70. Severity marker styles — planned/needs implementation, configuration, or validation.
71. Clustering for dense map points — planned/needs implementation, configuration, or validation.
72. Address geocoding provider — planned/needs implementation, configuration, or validation.
73. Reverse geocoding provider — planned/needs implementation, configuration, or validation.
74. Geofence-based ward assignment — planned/needs implementation, configuration, or validation.
75. Approximate public location display — planned/needs implementation, configuration, or validation.
76. Report search by ID — planned/needs implementation, configuration, or validation.
77. Advanced filters by date/category/status — planned/needs implementation, configuration, or validation.
78. PDF oversight report generation — planned/needs implementation, configuration, or validation.
79. Scheduled report delivery — planned/needs implementation, configuration, or validation.
80. Department performance comparisons — planned/needs implementation, configuration, or validation.
81. Median acknowledgement time KPI — planned/needs implementation, configuration, or validation.
82. Median resolution time KPI — planned/needs implementation, configuration, or validation.
83. SLA compliance KPI — planned/needs implementation, configuration, or validation.
84. Repeat complaint KPI — planned/needs implementation, configuration, or validation.
85. Closure evidence completeness KPI — planned/needs implementation, configuration, or validation.
86. Data freshness dashboard — planned/needs implementation, configuration, or validation.
87. Integration health dashboard — planned/needs implementation, configuration, or validation.
88. Disaster mode — planned/needs implementation, configuration, or validation.
89. Flood/heat incident workflow — planned/needs implementation, configuration, or validation.
90. Verified advisory expiry time — planned/needs implementation, configuration, or validation.
91. Grievance/appeal workflow — planned/needs implementation, configuration, or validation.
92. Accessibility keyboard review — planned/needs implementation, configuration, or validation.
93. High contrast theme — planned/needs implementation, configuration, or validation.
94. Low bandwidth mode — planned/needs implementation, configuration, or validation.
95. Multi-tenant municipality support — planned/needs implementation, configuration, or validation.
96. API for mobile/React clients — planned/needs implementation, configuration, or validation.
97. OpenAPI documentation — planned/needs implementation, configuration, or validation.
98. Automated end-to-end tests — planned/needs implementation, configuration, or validation.
99. Structured operational logging — planned/needs implementation, configuration, or validation.
100. Request correlation IDs — planned/needs implementation, configuration, or validation.
101. Monitoring and alerting — planned/needs implementation, configuration, or validation.
102. Security penetration test — planned/needs implementation, configuration, or validation.
103. Privacy impact assessment — planned/needs implementation, configuration, or validation.
104. Public deployment checklist — planned/needs implementation, configuration, or validation.

## Patent note

A feature list or AI application is not by itself proof of patentability. Before making novelty claims or filing, document the specific technical problem, new mechanism/algorithm, implementation details, measured comparison against prior approaches, and conduct a prior-art search with a qualified patent professional. Do not claim a public-health outbreak from unverified reports.

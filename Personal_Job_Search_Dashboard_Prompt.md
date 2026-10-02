# Personal Job Search Dashboard — Development Prompt

## Build a Personal Job Search Dashboard for Chad

Build a private, personal-use web application that acts as my personal job-search dashboard.

This application is **not** intended to be a public job board or multi-user platform.

It is designed specifically for my own job search and should permanently store my profile, skills, education, experience, portfolio projects, preferred jobs, and search criteria.

The primary purpose is:

> **When I open the dashboard and press Refresh Jobs, search available job sources for current openings, analyze them against my personal profile, and show me the 8 strongest current opportunities.**

If there are no meaningful new listings, continue displaying the strongest existing listings rather than leaving the dashboard empty.

---

# 1. Personal Profile

Hard-code or store my personal job-search profile in a configuration/database so the application does not ask me to enter it every time.

## Career Goal


Primary target:

- Entry-level Front-End Developer
- Junior Front-End Developer
- Entry-level Web Developer
- Junior Web Developer
- Web Designer / Developer
- Front-End Web Designer

Secondary acceptable roles:

- WordPress Designer
- WordPress Developer
- Website Coordinator
- Website Administrator
- Digital Content Specialist
- Ecommerce Website Specialist
- Junior UI Developer
- Web Content Specialist
- Digital Marketing/Web Specialist

Prioritize jobs that actually involve web development, web design, websites, frontend development, or digital web production.

Do not fill the dashboard with generic marketing jobs simply because they mention "website."

---

# 2. My Current Skills

Use the following as the baseline profile.

## Front-End

- HTML
- CSS
- JavaScript
- Responsive Web Design
- DOM manipulation
- Events
- Forms
- Basic JavaScript programming

## Frameworks / Development

- React
- Vite
- Basic Flask/Python
- Basic API concepts
- Basic database concepts

## CMS / Website Builders

- WordPress
- Elementor
- Blocksy
- Webflow

## Design

- Figma
- Adobe Photoshop
- Adobe Illustrator
- Adobe Creative Suite
- UI design
- Responsive layout
- Visual design

## Development Tools

- Git
- GitHub
- VS Code
- Vercel

The application should allow this profile to be edited later.

---

# 3. Education

Store my current education information.

I am pursuing an associate-level degree focused on web design/web development.

Relevant coursework includes areas such as:

- HTML
- CSS
- JavaScript
- Web Authoring
- Web Scripting
- Multimedia
- Digital Design
- Web Development

Education should be considered when analyzing whether a job's education requirements are satisfied.

---

# 4. Experience

The system should understand that my experience is a combination of:

- College coursework
- Personal development projects
- Portfolio projects
- Freelance/client website work
- Web design/development experience
- Previous professional experience involving project management, marketing, websites, and digital content

Do **not** falsely convert school or personal projects into professional employment.

Instead, distinguish between:

- Professional Experience
- Client/Freelance Experience
- Academic Experience
- Personal Projects

This distinction should be visible when explaining job matches.

---

# 5. Portfolio Projects

Store my portfolio projects and technologies.

Each project should contain:

- Project name
- Description
- Technologies
- Type of project
- URL
- Relevant skills demonstrated

Use portfolio projects when determining whether my experience is relevant to a job.

For example:

If a job requires responsive website development and JavaScript, a portfolio project demonstrating responsive JavaScript development should increase the relevance score.

---

# 6. Geographic Preferences

Primary search area:

**Lakeland, Florida**

Search nearby opportunities within a configurable radius.

Also search:

- Tampa
- Orlando
- Polk County
- Central Florida

Include:

- On-site
- Hybrid
- Remote

Remote jobs should be considered regardless of distance when the job is genuinely remote.

Make the geographic preferences configurable.

---

# 7. Refresh Jobs Button

The primary interaction should be:

## 🔄 Refresh Jobs

When I click this button:

1. Search configured job sources.
2. Retrieve current job postings.
3. Remove expired/inactive listings when possible.
4. Normalize the job data.
5. Remove duplicates.
6. Analyze every job against my personal profile.
7. Calculate the relevant scores.
8. Compare against jobs already stored.
9. Identify newly discovered jobs.
10. Rank all currently relevant jobs.
11. Display the strongest 8 opportunities.

Show:

> Last updated: October 2, 2026 at 1:05 PM

And while refreshing:

> Searching for new opportunities...

---

# 8. Do Not Randomly Replace Jobs

This is extremely important.

The dashboard should **not** simply display the eight newest jobs.

Instead, rank jobs based on how closely they match my profile.

The system should prefer:

1. Strong skill match
2. Appropriate experience level
3. Entry-level/junior designation
4. Relevant portfolio compatibility
5. Reasonable geographic compatibility
6. Education compatibility
7. Reasonable application requirements
8. Freshness of listing

A new job should replace an existing job only if it represents a meaningful improvement or is a new highly relevant opportunity.

---

# 9. Always Show 8 Jobs When Possible

The dashboard should attempt to maintain a list of **8 strong opportunities**.

If there are new qualified listings:

Show the strongest 8.

If there are not enough new listings:

Continue showing strong existing listings from the database.

For example:

### Today

3 new strong jobs found.

The remaining 5 positions can come from previously discovered jobs that:

- Are still active
- Still closely match my profile
- Have not already been rejected
- Have not expired
- Have not already been marked as irrelevant

This prevents the dashboard from becoming empty simply because there weren't eight new postings today.

---

# 10. Job Lifecycle

Every discovered job should have a status.

Possible statuses:

- New
- Viewed
- Saved
- Applied
- Interview
- Rejected
- Expired
- Hidden
- No Longer Relevant

Once I mark a job as:

**Rejected**

do not put it back into the primary 8.

Once I mark a job as:

**Applied**

keep it in the application tracker but do not repeatedly recommend it as a new opportunity.

---

# 11. The 8 Main Job Cards

The main dashboard should display exactly eight cards when eight qualifying jobs are available.

Each card should show:

### Job Title

### Company

### Location

### Work Arrangement

Remote / Hybrid / On-site

### Salary

If available.

### Date Posted

### Job Fit

Example:

**87% Strong Match**

### Application Difficulty

Example:

🟡 Moderate

### Interview Competitiveness

Example:

🟠 Higher Competition

### Hiring Context

Example:

🟢 Appears Accessible to Entry-Level Candidates

### Match Summary

A short explanation of why the job matches my profile.

### Main Strengths

Example:

- HTML/CSS
- JavaScript
- React
- Responsive design

### Main Gaps

Example:

- TypeScript
- 1 year professional experience

### Portfolio Relevance

Explain which of my projects are relevant.

### Application Link

**[Apply]**

---

# 12. Job Ranking Algorithm

Create a transparent ranking system.

Do **not** claim that the ranking predicts whether I will actually get hired.

Instead, create an:

## Application Fit Score

The score should consider:

### Required Skill Match — 40%

How many required skills do I possess?

### Experience Match — 20%

Does the required experience level match my current experience?

### Portfolio Relevance — 15%

Do my portfolio/client projects demonstrate relevant skills?

### Education Match — 10%

Do I meet the stated education requirements?

### Job Level — 10%

Does the job genuinely appear entry-level/junior?

### Location/Work Arrangement — 5%

Does it fit my geographic preferences?

These weights should be configurable.

---

# 13. Application Difficulty

Calculate separately from Job Fit.

Difficulty should consider:

- Years of experience requested
- Number of required technologies
- Specialized technologies
- Degree requirements
- Certifications
- Seniority
- Professional experience requirements
- Number of missing required skills

Categories:

- 🟢 Low
- 🟡 Moderate
- 🟠 High
- 🔴 Very High

Explain the reason.

Example:

> Moderate — The position is listed as junior and matches most of your technical skills, but the employer requests 1 year of professional experience and TypeScript.

---

# 14. Interview Competitiveness

Create a separate measurement.

This should **not** claim:

> "You have a 70% chance of getting an interview."

Instead determine whether the available evidence suggests the position is likely to be more or less competitive for someone with my profile.

Consider:

- Experience requirements
- Seniority
- Required technologies
- Degree requirements
- Specialized qualifications
- Public application-volume information when available
- Publicly available candidate/interview information
- Whether the employer appears to hire junior candidates
- Whether the company frequently posts junior positions
- Whether the job is unusually specialized

Use:

- 🟢 Lower apparent competition
- 🟡 Moderate competition
- 🟠 Higher competition
- 🔴 Very competitive
- ⚪ Insufficient evidence

If there isn't enough evidence:

> **Insufficient evidence**

Never fabricate hiring statistics.

---

# 15. Company Hiring Context

For each company, when sufficient public information exists, determine whether there is evidence that the company:

- Hires junior developers
- Hires entry-level candidates
- Accepts equivalent experience
- Offers internships
- Offers apprenticeships
- Has junior-level positions
- Has a history of hiring candidates with limited professional experience
- Commonly requires several years of experience

Display:

### Company Hiring Context

Example:

- 🟢 Entry-Level Friendly Evidence
- 🟡 Mixed Evidence
- 🟠 Experience Focused
- ⚪ Insufficient Evidence

Include a short explanation.

Example:

> The company has publicly posted multiple junior-level web positions and internship opportunities. However, this specific position requests 2 years of experience.

Do not claim that a company is "easy to get hired by."

---

# 16. Search Sources

Create a configurable list of job sources.

The application should use APIs, feeds, or other permitted access methods whenever available.

Do **not** build the system around unauthorized scraping or methods that violate a site's terms of service.

Potential sources can include:

- Job APIs
- Company career pages
- Public job feeds
- Other permitted employment data sources

Store the original source and application URL.

---

# 17. Duplicate Detection

The same job may appear on multiple sources.

Detect duplicates using combinations of:

- Company
- Job title
- Location
- Job description
- Application URL
- Job ID

Combine duplicate records where appropriate.

Prefer the company's direct application URL when available.

---

# 18. Freshness System

Each job should have:

- Date discovered
- Original posting date
- Last checked
- Last confirmed active
- Source

A job that hasn't been confirmed active for a configurable period should be flagged.

Example:

> ⚠ Listing may be stale

Do not continuously display old jobs simply to fill the eight slots.

---

# 19. Personal Job History

Track:

- Jobs viewed
- Jobs saved
- Jobs applied to
- Interviews
- Rejections
- Offers

Eventually calculate personal statistics such as:

- Applications submitted
- Interviews received
- Interview rate
- Applications by job type
- Applications by company type
- Most common missing skills
- Average fit score of applications
- Which skills appear most frequently in jobs

These statistics should be based only on my actual application history.

---

# 20. Learning Gap Analysis

The system should identify recurring missing skills across the jobs it finds.

Example:

After analyzing 50 relevant jobs:

> **Most Requested Skills You Are Missing**

1. TypeScript — appears in 34% of relevant jobs
2. Testing — 27%
3. Next.js — 22%
4. Tailwind — 19%

This gives me a data-driven way to decide what to learn next.

Do not tell me that I "must" learn something solely because it appears frequently. Show the evidence and let me decide.

---

# 21. Main Dashboard Layout

The homepage should contain:

## JOB SEARCH

**Last refreshed:** 12 minutes ago

**[ 🔄 Refresh Jobs ]**

### Current Opportunities

**8 Strong Matches**

Then the eight job cards.

---

## Search Summary

Example:

- Jobs scanned: 184
- Relevant jobs: 37
- New jobs: 6
- Strong matches: 12
- Displayed: 8

---

## Your Job Market

Show:

- Most requested skills
- Common experience requirements
- Common salary ranges
- Number of entry-level opportunities
- Most common job titles

---

## Application Tracker

Show:

- Applied: 14
- Interviews: 3
- Rejected: 7
- Active: 4

---

# 22. Persistent Database

The application needs persistent storage.

## Jobs

Store:

- ID
- Title
- Company
- Description
- URL
- Source
- Location
- Salary
- Date posted
- Date discovered
- Last checked
- Status
- Fit score
- Difficulty
- Competitiveness
- Analysis

## User Profile

Store:

- Skills
- Education
- Experience
- Projects
- Locations
- Job preferences

## Applications

Store:

- Job ID
- Status
- Date applied
- Interview dates
- Notes

---

# 23. Important Principle

The dashboard is **not trying to predict who will hire me**.

It is trying to answer:

> **"Out of the jobs currently available, which eight appear to have the strongest evidence of being a realistic match for my current qualifications?"**

Every ranking must be explainable.

Every score must have supporting factors.

Every uncertain conclusion must be labeled as uncertain.

Never fabricate missing information.

---

# 24. Future AI Integration

Design the architecture so an AI model can eventually analyze job descriptions.

AI can help with:

- Extracting required skills
- Identifying experience requirements
- Comparing job requirements against my profile
- Summarizing why a job matches
- Identifying missing skills
- Detecting misleading "entry-level" listings
- Summarizing publicly available company hiring information

The AI should **not** invent facts.

Store the raw job description so the analysis can always be traced back to the source.

---

# 25. Final Product Goal

When I open the application, I should immediately see:

> **"Here are the 8 strongest currently available jobs for you."**

I should not have to manually search Indeed, LinkedIn, Google, company websites, etc. every time.

I press:

**🔄 Refresh Jobs**

The application searches for new opportunities, analyzes them against my existing profile, updates the database, removes stale jobs, and presents the strongest eight currently available opportunities.

If there aren't eight new opportunities, it intelligently keeps the strongest previously discovered active jobs.

The application should feel like a **personal job-search agent/dashboard**, not a generic job board.

# Analysis of Each MLB Projection System and Fantasy Baseball Projections (2025-2026)

Scraps Yahoo Fantasy ADP data and Fangraphs projected stats from each projection system with Selenium.

Compared the performance of the last 3 years of each MLB projection system available on Fangraphs (as of March of 2026), and create an aggregate projection of selected players based on which system performs best in each stat.

Created a new stat called Optimal Pull Flyball% to experiment with projections (2025). I defined an "Optimal Pulled Flyball" as a ball hit over 200 feet with launch angle between 22-42 degrees. The idea is that this could filter out players who hit a lot of pulled flyballs but also a lot of pulled popups, experiments show limited effects in simple regression and tree-based models.

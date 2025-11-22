"""
COMPREHENSIVE IMPROVED BET365 EXTRACTION SCRIPT
Supports all sports including Cricket (horizontal markets), Sets-based sports (Badminton, Volleyball, Table Tennis)

To use: Replace the extraction_script variable in playwright_bet365_live.py (around line 1465)
"""

def get_comprehensive_extraction_script(sport_code, sport_mappings_js, match_selectors_js, 
                                        team_selectors_js, score_selectors_js, 
                                        odds_selectors_js, status_selectors_js):
    """
    Generate comprehensive extraction script supporting all Bet365 sports with intelligent sport detection

    Key features:
    - Standard market structure (.ovm-MarketGroup)
    - Cricket horizontal market structure (.ovm-HorizontalMarket)
    - Sets-based scores (.ovm-SetsBasedScores)
    - Cricket scores (.ovm-StandardScoresCricket)
    - Standard scores (.ovm-StandardScores)
    - INTELLIGENT SPORT DETECTION: Detects actual sport from team names and content, not just URL

    Args:
        sport_code: Bet365 sport code (e.g., 'B18', 'B1', 'B3')
        sport_mappings_js: JSON string of sport code to name mappings
        match_selectors_js: JSON string of fixture container selectors
        team_selectors_js: JSON string of team name selectors
        score_selectors_js: JSON string of score selectors
        odds_selectors_js: JSON string of odds selectors
        status_selectors_js: JSON string of status/timer selectors

    Returns:
        Complete JavaScript extraction function as string
    """
    
    return f"""
(function() {{
    try {{
        console.log('=== COMPREHENSIVE BET365 EXTRACTION ===');
        console.log('Sport Code: {sport_code}');
        
        // Configuration
        const SPORT_CODE = '{sport_code}';
        const SPORT_MAPPINGS = JSON.parse('{sport_mappings_js}');
        const CURRENT_SPORT_NAME = SPORT_MAPPINGS[SPORT_CODE] || 'Unknown';
        
        // Comprehensive Market Layouts by Sport
        const MARKET_LAYOUTS = {{
            // 3-Column Sports: Spread | Total | Money
            'B18': {{ columns: ['spread', 'total', 'moneyline'], type: 'standard' }},      // Basketball
            'B16': {{ columns: ['spread', 'total', 'moneyline'], type: 'standard' }},      // Baseball
            'B21': {{ columns: ['spread', 'total', 'moneyline'], type: 'standard' }},      // NFL
            'B12': {{ columns: ['spread', 'total', 'moneyline'], type: 'standard' }},      // American Football
            'B17': {{ columns: ['spread', 'total', 'moneyline'], type: 'standard' }},      // NHL
            'B151': {{ columns: ['spread', 'total', 'moneyline'], type: 'standard' }},     // Esports
            
            // Soccer: Home | Tie | Away
            'B1': {{ columns: ['home', 'tie', 'away'], type: 'standard' }},
            
            // Tennis: 2-Way
            'B13': {{ columns: ['player1', 'player2'], type: 'standard' }},
            
            // Cricket: Horizontal Market (special handling)
            'B3': {{ columns: ['team1', 'draw', 'team2'], type: 'horizontal' }},
            
            // Sets-based Sports
            'B91': {{ columns: ['match', 'set', 'set_total'], type: 'standard', uses_sets: true }},     // Volleyball
            'B92': {{ columns: ['moneyline', 'game', 'game_total'], type: 'standard', uses_sets: true }}, // Table Tennis
            'B94': {{ columns: ['to win', 'game', 'game_total'], type: 'standard', uses_sets: true }}, // Badminton
            
            // Special layouts
            'B78': {{ columns: ['spread', 'total', 'tie_no_bet'], type: 'standard' }},     // Handball
            'B1002': {{ columns: ['spread', 'total', 'tie_no_bet'], type: 'standard' }}    // Futsal
        }};
        
        const LAYOUT = MARKET_LAYOUTS[SPORT_CODE] || {{ columns: ['spread', 'total', 'moneyline'], type: 'standard' }};
        console.log('Layout:', LAYOUT);
        
        // Results structure
        const results = {{
            sport_code: SPORT_CODE,
            sport_name: CURRENT_SPORT_NAME,
            matches: [],
            summary: {{
                total_matches: 0,
                total_markets: 0,
                total_odds: 0
            }},
            debug: {{
                selectors_tried: [],
                extraction_time: new Date().toISOString(),
                market_debug: [],
                sport_detection: {{
                    requested_sport: CURRENT_SPORT_NAME,
                    detected_sport: null,
                    confidence: 0,
                    reasoning: []
                }}
            }}
        }};
        
        // Find all fixtures
        const fixtureSelectors = JSON.parse('{match_selectors_js}');
        let fixtures = [];

        for (const selector of fixtureSelectors) {{
            fixtures = document.querySelectorAll(selector);
            if (fixtures.length > 0) {{
                console.log(`Found ${{fixtures.length}} fixtures using: ${{selector}}`);
                results.debug.selectors_tried.push(`FIXTURES:${{selector}}:${{fixtures.length}}`);
                break;
            }}
        }}
        
        if (fixtures.length === 0) {{
            console.log('No fixtures found');
            console.log('=== FINAL DEBUG INFO ===');
            console.log('Market debug:', results.debug.market_debug);
            console.log('Selectors tried:', results.debug.selectors_tried);
    
            return results;
        }}
        
        // Process each fixture
        fixtures.forEach((fixture, index) => {{
            console.log(`\\n=== FIXTURE ${{index + 1}} ===`);
            
            const matchData = {{
                fixture_index: index + 1,
                teams: {{ home: '', away: '' }},
                scores: {{ home: '0', away: '0' }},
                sets_scores: {{ home: '0', away: '0', points_home: '0', points_away: '0' }},
                time: 'Live',
                status: 'Live',
                period: '',
                markets: {{}},
                live_fields: {{
                    is_live: true,
                    time_remaining: '',
                    match_status: 'Live'
                }}
            }};
            
            // ==========================================
            // 1. EXTRACT TEAM NAMES
            // ==========================================
            try {{
                console.log('[TEAMS] Starting extraction...');
                
                // Try multiple team selector patterns
                const teamSelectors = [
                    '.ovm-FixtureDetailsTwoWay_TeamName',
                    '.ovm-FixtureDetailsWithIndicators_Team',
                    '.ovm-FixtureDetailsTwoWayAmericanFootball_TeamName',
                    '.ovm-FixtureDetailsBaseball_Teams',
                    '[class*="TeamName"]'
                ];
                
                let teamElements = [];
                for (const selector of teamSelectors) {{
                    teamElements = fixture.querySelectorAll(selector);
                    if (teamElements.length >= 2) {{
                        console.log(`[TEAMS] Using selector: ${{selector}}`);
                        break;
                    }}
                }}
                
                if (teamElements.length >= 2) {{
                    matchData.teams.home = teamElements[0].textContent.trim();
                    matchData.teams.away = teamElements[1].textContent.trim();
                    console.log(`[TEAMS] ${{matchData.teams.home}} vs ${{matchData.teams.away}}`);
                }} else {{
                    console.log('[TEAMS] Could not find team names');
                }}
            }} catch (e) {{
                console.log('[TEAMS] Error:', e.message);
            }}
            
            // ==========================================
            // 2. EXTRACT SCORES (SPORT-SPECIFIC)
            // ==========================================
            try {{
                console.log('[SCORES] Starting extraction...');

                // CRICKET SCORES (special format)
                if (SPORT_CODE === 'B3') {{
                    const homeScoreEl = fixture.querySelector('.ovm-StandardScoresCricket_TeamOne');
                    const awayScoreEl = fixture.querySelector('.ovm-StandardScoresCricket_TeamTwo');

                    if (homeScoreEl) {{
                        matchData.scores.home = homeScoreEl.textContent.trim();
                        console.log(`[SCORES] Cricket home: ${{matchData.scores.home}}`);
                    }}
                    if (awayScoreEl) {{
                        matchData.scores.away = awayScoreEl.textContent.trim();
                        console.log(`[SCORES] Cricket away: ${{matchData.scores.away}}`);
                    }}
                }}
                // TENNIS SCORES (special complex structure)
                else if (SPORT_CODE === 'B13') {{
                    const tennisScores = fixture.querySelector('.ovm-SetsBasedScoresTennis');

                    if (tennisScores) {{
                        // Extract sets won
                        const setsHome = tennisScores.querySelector('.ovm-SetsBasedScoresTennis_SetsWrapper .ovm-SetsBasedScoresTennis_TeamOne');
                        const setsAway = tennisScores.querySelector('.ovm-SetsBasedScoresTennis_SetsWrapper .ovm-SetsBasedScoresTennis_TeamTwo');

                        // Extract games in current set
                        const gamesHome = tennisScores.querySelector('.ovm-SetsBasedScoresTennis_SetsGamesCol .ovm-SetsBasedScoresTennis_TeamOne');
                        const gamesAway = tennisScores.querySelector('.ovm-SetsBasedScoresTennis_SetsGamesCol .ovm-SetsBasedScoresTennis_TeamTwo');

                        // Extract points in current game
                        const pointsHome = tennisScores.querySelector('.ovm-SetsBasedScoresTennis_PointsWrapper .ovm-SetsBasedScoresTennis_TeamOne');
                        const pointsAway = tennisScores.querySelector('.ovm-SetsBasedScoresTennis_PointsWrapper .ovm-SetsBasedScoresTennis_TeamTwo');

                        // Format tennis score: "sets-sets (games-games) [points-points]"
                        const setsH = setsHome?.textContent?.trim() || '0';
                        const setsA = setsAway?.textContent?.trim() || '0';
                        const gamesH = gamesHome?.textContent?.trim() || '0';
                        const gamesA = gamesAway?.textContent?.trim() || '0';
                        const pointsH = pointsHome?.textContent?.trim() || '0';
                        const pointsA = pointsAway?.textContent?.trim() || '0';

                        // Create tennis score format: "sets-sets (games-games) [points-points]"
                        const tennisScore = `${{setsH}}-${{setsA}} (${{gamesH}}-${{gamesA}}) [${{pointsH}}-${{pointsA}}]`;
                        matchData.scores.home = tennisScore;
                        matchData.scores.away = ''; // Tennis scores are combined

                        console.log(`🎾 TENNIS SCORE: ${{tennisScore}}`);
                    }} else {{
                        // Fallback: Extract from set/game label if tennis scores not found
                        const setGameLabel = fixture.querySelector('.ovm-FixtureDetailsWithIndicators_SetGameLabel');
                        if (setGameLabel) {{
                            const labelText = setGameLabel.textContent.trim();
                            console.log(`🎾 TENNIS FALLBACK: Using set/game label: ${{labelText}}`);
                            matchData.scores.home = labelText;
                            matchData.scores.away = '';
                        }}
                    }}
                }}
                // SETS-BASED SCORES (Badminton, Volleyball, Table Tennis)
                else if (LAYOUT.uses_sets) {{
                    const setsWrapper = fixture.querySelector('.ovm-SetsBasedScores');

                    if (setsWrapper) {{
                        // Extract sets
                        const setsInner = setsWrapper.querySelector('.ovm-SetsBasedScores_SetsInner');
                        if (setsInner) {{
                            const homeSetEl = setsInner.querySelector('.ovm-SetsBasedScores_TeamOne');
                            const awaySetEl = setsInner.querySelector('.ovm-SetsBasedScores_TeamTwo');

                            if (homeSetEl && awaySetEl) {{
                                matchData.sets_scores.home = homeSetEl.textContent.trim();
                                matchData.sets_scores.away = awaySetEl.textContent.trim();
                                console.log(`[SCORES] Sets: ${{matchData.sets_scores.home}} - ${{matchData.sets_scores.away}}`);
                            }}
                        }}

                        // Extract points (current game/set)
                        const pointsWrapper = setsWrapper.querySelector('.ovm-SetsBasedScores_PointsWrapper');
                        if (pointsWrapper) {{
                            const homePointsEl = pointsWrapper.querySelector('.ovm-SetsBasedScores_TeamOne');
                            const awayPointsEl = pointsWrapper.querySelector('.ovm-SetsBasedScores_TeamTwo');

                            if (homePointsEl && awayPointsEl) {{
                                matchData.sets_scores.points_home = homePointsEl.textContent.trim();
                                matchData.sets_scores.points_away = awayPointsEl.textContent.trim();
                                console.log(`[SCORES] Points: ${{matchData.sets_scores.points_home}} - ${{matchData.sets_scores.points_away}}`);
                            }}
                        }}

                        // For sets-based sports, use sets_scores as the primary score display
                        // Format: "sets-points" (e.g., "1-11" for badminton)
                        if (matchData.sets_scores.home !== '0' || matchData.sets_scores.away !== '0') {{
                            matchData.scores.home = `${{matchData.sets_scores.home}}-${{matchData.sets_scores.points_home}}`;
                            matchData.scores.away = `${{matchData.sets_scores.away}}-${{matchData.sets_scores.points_away}}`;
                        }} else {{
                            // If no sets yet, just show points
                            matchData.scores.home = matchData.sets_scores.points_home;
                            matchData.scores.away = matchData.sets_scores.points_away;
                        }}
                    }} else {{
                        // Fallback: Try to extract odds directly for Badminton
                        if (SPORT_CODE === 'B94') {{
                            console.log('[SCORES] Badminton: No sets wrapper found, trying direct odds extraction');
                            // Badminton might have odds but no scores - that's normal
                            matchData.scores.home = '0';
                            matchData.scores.away = '0';
                        }}
                    }}
                }}
                // STANDARD SCORES (Basketball, Baseball, Soccer, etc.)
                else {{
                    let homeScoreEl = fixture.querySelector('.ovm-StandardScores_TeamOne');
                    let awayScoreEl = fixture.querySelector('.ovm-StandardScores_TeamTwo');

                    if (homeScoreEl && awayScoreEl) {{
                        matchData.scores.home = homeScoreEl.textContent.trim();
                        matchData.scores.away = awayScoreEl.textContent.trim();
                        console.log(`[SCORES] Standard: ${{matchData.scores.home}} - ${{matchData.scores.away}}`);
                        results.debug.selectors_tried.push('SCORES:StandardScores:success');
                    }} else {{
                        // Try soccer-specific selectors
                        homeScoreEl = fixture.querySelector('.ovm-StandardScoresSoccer_TeamOne');
                        awayScoreEl = fixture.querySelector('.ovm-StandardScoresSoccer_TeamTwo');

                        if (homeScoreEl && awayScoreEl) {{
                            matchData.scores.home = homeScoreEl.textContent.trim();
                            matchData.scores.away = awayScoreEl.textContent.trim();
                            console.log(`[SCORES] Soccer: ${{matchData.scores.home}} - ${{matchData.scores.away}}`);
                            results.debug.selectors_tried.push('SCORES:StandardScoresSoccer:success');
                        }}
                    }}

                    // Remove sets_scores for non-sets sports
                    delete matchData.sets_scores;
                }}

            }} catch (e) {{
                console.log('[SCORES] Error:', e.message);
            }}
            
            // ==========================================
            // 3. EXTRACT TIME/STATUS
            // ==========================================
            try {{
                const statusSelectors = {status_selectors_js};
                let timerEl = null;
                
                for (const selector of statusSelectors) {{
                    timerEl = fixture.querySelector(selector);
                    if (timerEl) {{
                        console.log(`[TIME] Using selector: ${{selector}}`);
                        break;
                    }}
                }}
                
                if (timerEl) {{
                    const timeText = timerEl.textContent.trim();
                    matchData.time = timeText;
                    matchData.live_fields.time_remaining = timeText;
                    
                    // Determine status
                    if (/^(FT|Full Time|Final)$/i.test(timeText)) {{
                        matchData.status = 'Finished';
                        matchData.live_fields.is_live = false;
                    }} else if (/^(HT|Half Time)$/i.test(timeText)) {{
                        matchData.status = 'HalfTime';
                        matchData.period = 'HT';
                    }} else {{
                        matchData.status = 'Live';
                    }}
                    
                    console.log(`[TIME] ${{timeText}} (Status: ${{matchData.status}})`);
                }}
            }} catch (e) {{
                console.log('[TIME] Error:', e.message);
            }}
            
            // ==========================================
            // 4. EXTRACT ODDS (LAYOUT-AWARE)
            // ==========================================
            try {{
                console.log('[ODDS] Starting extraction...');

                // CRICKET: Uses horizontal market structure
                if (LAYOUT.type === 'horizontal') {{
                    console.log('[ODDS] Using horizontal market extraction (Cricket)');

                    const horizontalMarket = fixture.querySelector('.ovm-HorizontalMarket');

                    if (horizontalMarket) {{
                        const participants = horizontalMarket.querySelectorAll('.ovm-HorizontalMarket_Participant');
                        console.log(`[ODDS] Found ${{participants.length}} horizontal participants`);

                        if (participants.length >= 2) {{
                            const odds = [];
                            participants.forEach(participant => {{
                                const oddsEl = participant.querySelector('.ovm-ParticipantOddsOnly_Odds');
                                if (oddsEl) {{
                                    odds.push(oddsEl.textContent.trim());
                                }}
                            }});

                            console.log('[ODDS] Cricket odds:', odds);

                            // 3-way (with draw)
                            if (odds.length >= 3) {{
                                matchData.markets.moneyline = {{
                                    home: {{ odds: odds[0] }},
                                    draw: {{ odds: odds[1] }},
                                    away: {{ odds: odds[2] }}
                                }};
                                results.summary.total_odds += 3;
                            }}
                            // 2-way (no draw)
                            else if (odds.length >= 2) {{
                                matchData.markets.moneyline = {{
                                    home: {{ odds: odds[0] }},
                                    away: {{ odds: odds[1] }}
                                }};
                                results.summary.total_odds += 2;
                            }}
                        }}
                    }}
                }}
                // SPECIAL HANDLING FOR BADMINTON: Extract odds directly from market group
                else if (SPORT_CODE === 'B94') {{
                    console.log('[BADMINTON] Starting direct badminton odds extraction');

                    const marketGroup = fixture.querySelector('.ovm-MarketGroup');
                    if (marketGroup) {{
                        console.log('[BADMINTON] Found market group for badminton');

                        // Get all market elements
                        const marketElements = marketGroup.querySelectorAll('.ovm-Market');
                        console.log(`[BADMINTON] Found ${{marketElements.length}} market elements`);

                        marketElements.forEach((market, marketIndex) => {{
                            console.log(`[BADMINTON] Processing market ${{marketIndex + 1}}`);

                            if (marketIndex === 0) {{
                                // Moneyline market - To Win
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[BADMINTON] Moneyline odds found: ${{oddsElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Odds ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2) {{
                                    if (!matchData.markets.moneyline) {{
                                        matchData.markets.moneyline = {{}};
                                    }}
                                    matchData.markets.moneyline.home = {{ odds: oddsElements[0].textContent.trim() }};
                                    matchData.markets.moneyline.away = {{ odds: oddsElements[1].textContent.trim() }};
                                    matchData.has_odds = true;
                                    results.summary.total_odds += 2;
                                    console.log(`[BADMINTON] Set moneyline: home=${{oddsElements[0].textContent.trim()}}, away=${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 1) {{
                                // Handicap market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[BADMINTON] Handicap odds found: ${{oddsElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Odds ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2) {{
                                    matchData.markets.handicap = {{
                                        home: {{ odds: oddsElements[0].textContent.trim() }},
                                        away: {{ odds: oddsElements[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[BADMINTON] Set handicap: home=${{oddsElements[0].textContent.trim()}}, away=${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 2) {{
                                // Total market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantStackedCentered_Odds');
                                const linesElements = market.querySelectorAll('.ovm-ParticipantStackedCentered_Handicap');
                                console.log(`[BADMINTON] Total odds: ${{oddsElements.length}}, lines: ${{linesElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Total Odds ${{i}}: "${{el.textContent.trim()}}"`));
                                linesElements.forEach((el, i) => console.log(`  Total Lines ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2 && linesElements.length >= 2) {{
                                    const overLine = linesElements[0].textContent.trim().replace('O', '').trim();
                                    const underLine = linesElements[1].textContent.trim().replace('U', '').trim();

                                    matchData.markets.total = {{
                                        over: {{ line: overLine, odds: oddsElements[0].textContent.trim() }},
                                        under: {{ line: underLine, odds: oddsElements[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[BADMINTON] Set total: over=${{overLine}}@${{oddsElements[0].textContent.trim()}}, under=${{underLine}}@${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }}
                        }});
                    }} else {{
                        console.log('[BADMINTON] No market group found for badminton');
                    }}
                }}
                // SPECIAL HANDLING FOR VOLLEYBALL: Extract odds directly from market group
                else if (SPORT_CODE === 'B91') {{
                    console.log('[VOLLEYBALL] Starting direct volleyball odds extraction');

                    const marketGroup = fixture.querySelector('.ovm-MarketGroup');
                    if (marketGroup) {{
                        console.log('[VOLLEYBALL] Found market group for volleyball');

                        // Get all market elements
                        const marketElements = marketGroup.querySelectorAll('.ovm-Market');
                        console.log(`[VOLLEYBALL] Found ${{marketElements.length}} market elements`);

                        marketElements.forEach((market, marketIndex) => {{
                            console.log(`[VOLLEYBALL] Processing market ${{marketIndex + 1}}`);

                            if (marketIndex === 0) {{
                                // Match Moneyline market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[VOLLEYBALL] Moneyline odds found: ${{oddsElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Odds ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2) {{
                                    if (!matchData.markets.moneyline) {{
                                        matchData.markets.moneyline = {{}};
                                    }}
                                    matchData.markets.moneyline.home = {{ odds: oddsElements[0].textContent.trim() }};
                                    matchData.markets.moneyline.away = {{ odds: oddsElements[1].textContent.trim() }};
                                    matchData.has_odds = true;
                                    results.summary.total_odds += 2;
                                    console.log(`[VOLLEYBALL] Set moneyline: home=${{oddsElements[0].textContent.trim()}}, away=${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 1) {{
                                // Set Handicap market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[VOLLEYBALL] Handicap odds found: ${{oddsElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Odds ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2) {{
                                    matchData.markets.handicap = {{
                                        home: {{ odds: oddsElements[0].textContent.trim() }},
                                        away: {{ odds: oddsElements[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[VOLLEYBALL] Set handicap: home=${{oddsElements[0].textContent.trim()}}, away=${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 2) {{
                                // Set Total market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantStackedCentered_Odds');
                                const linesElements = market.querySelectorAll('.ovm-ParticipantStackedCentered_Handicap');
                                console.log(`[VOLLEYBALL] Total odds: ${{oddsElements.length}}, lines: ${{linesElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Total Odds ${{i}}: "${{el.textContent.trim()}}"`));
                                linesElements.forEach((el, i) => console.log(`  Total Lines ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2 && linesElements.length >= 2) {{
                                    const overLine = linesElements[0].textContent.trim().replace('O', '').trim();
                                    const underLine = linesElements[1].textContent.trim().replace('U', '').trim();

                                    matchData.markets.total = {{
                                        over: {{ line: overLine, odds: oddsElements[0].textContent.trim() }},
                                        under: {{ line: underLine, odds: oddsElements[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[VOLLEYBALL] Set total: over=${{overLine}}@${{oddsElements[0].textContent.trim()}}, under=${{underLine}}@${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }}
                        }});
                    }} else {{
                        console.log('[VOLLEYBALL] No market group found for volleyball');
                    }}
                }}
                // SPECIAL HANDLING FOR DARTS: Extract odds directly from market group
                else if (SPORT_CODE === 'B15') {{
                    console.log('[DARTS] Starting direct darts odds extraction');

                    const marketGroup = fixture.querySelector('.ovm-MarketGroup');
                    if (marketGroup) {{
                        console.log('[DARTS] Found market group for darts');

                        // Get all market elements
                        const marketElements = marketGroup.querySelectorAll('.ovm-Market');
                        console.log(`[DARTS] Found ${{marketElements.length}} market elements`);

                        marketElements.forEach((market, marketIndex) => {{
                            console.log(`[DARTS] Processing market ${{marketIndex + 1}}`);

                            if (marketIndex === 0) {{
                                // Moneyline market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[DARTS] Moneyline odds found: ${{oddsElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Odds ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2) {{
                                    if (!matchData.markets.moneyline) {{
                                        matchData.markets.moneyline = {{}};
                                    }}
                                    matchData.markets.moneyline.home = {{ odds: oddsElements[0].textContent.trim() }};
                                    matchData.markets.moneyline.away = {{ odds: oddsElements[1].textContent.trim() }};
                                    matchData.has_odds = true;
                                    results.summary.total_odds += 2;
                                    console.log(`[DARTS] Set moneyline: home=${{oddsElements[0].textContent.trim()}}, away=${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 1) {{
                                // Next Leg market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[DARTS] Next Leg odds found: ${{oddsElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Odds ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2) {{
                                    matchData.markets.next_leg = {{
                                        home: {{ odds: oddsElements[0].textContent.trim() }},
                                        away: {{ odds: oddsElements[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[DARTS] Set next leg: home=${{oddsElements[0].textContent.trim()}}, away=${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 2) {{
                                // 180s market (total)
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantStackedCentered_Odds');
                                const linesElements = market.querySelectorAll('.ovm-ParticipantStackedCentered_Handicap');
                                console.log(`[DARTS] 180s odds: ${{oddsElements.length}}, lines: ${{linesElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  180s Odds ${{i}}: "${{el.textContent.trim()}}"`));
                                linesElements.forEach((el, i) => console.log(`  180s Lines ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2 && linesElements.length >= 2) {{
                                    const overLine = linesElements[0].textContent.trim().replace('O', '').trim();
                                    const underLine = linesElements[1].textContent.trim().replace('U', '').trim();

                                    matchData.markets.total_180s = {{
                                        over: {{ line: overLine, odds: oddsElements[0].textContent.trim() }},
                                        under: {{ line: underLine, odds: oddsElements[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[DARTS] Set 180s total: over=${{overLine}}@${{oddsElements[0].textContent.trim()}}, under=${{underLine}}@${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }}
                        }});
                    }} else {{
                        console.log('[DARTS] No market group found for darts');
                    }}
                }}
                // SPECIAL HANDLING FOR SNOOKER: Extract odds directly from market group
                else if (SPORT_CODE === 'B14') {{
                    console.log('[SNOOKER] Starting direct snooker odds extraction');

                    const marketGroup = fixture.querySelector('.ovm-MarketGroup');
                    if (marketGroup) {{
                        console.log('[SNOOKER] Found market group for snooker');

                        // Get all market elements
                        const marketElements = marketGroup.querySelectorAll('.ovm-Market');
                        console.log(`[SNOOKER] Found ${{marketElements.length}} market elements`);

                        marketElements.forEach((market, marketIndex) => {{
                            console.log(`[SNOOKER] Processing market ${{marketIndex + 1}}`);

                            if (marketIndex === 0) {{
                                // Moneyline market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[SNOOKER] Moneyline odds found: ${{oddsElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Odds ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2) {{
                                    if (!matchData.markets.moneyline) {{
                                        matchData.markets.moneyline = {{}};
                                    }}
                                    matchData.markets.moneyline.home = {{ odds: oddsElements[0].textContent.trim() }};
                                    matchData.markets.moneyline.away = {{ odds: oddsElements[1].textContent.trim() }};
                                    matchData.has_odds = true;
                                    results.summary.total_odds += 2;
                                    console.log(`[SNOOKER] Set moneyline: home=${{oddsElements[0].textContent.trim()}}, away=${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 1) {{
                                // Current Frame market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[SNOOKER] Current Frame odds found: ${{oddsElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Odds ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2) {{
                                    matchData.markets.current_frame = {{
                                        home: {{ odds: oddsElements[0].textContent.trim() }},
                                        away: {{ odds: oddsElements[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[SNOOKER] Set current frame: home=${{oddsElements[0].textContent.trim()}}, away=${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 2) {{
                                // Next Frame market
                                const oddsElements = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[SNOOKER] Next Frame odds found: ${{oddsElements.length}}`);
                                oddsElements.forEach((el, i) => console.log(`  Odds ${{i}}: "${{el.textContent.trim()}}"`));

                                if (oddsElements.length >= 2) {{
                                    matchData.markets.next_frame = {{
                                        home: {{ odds: oddsElements[0].textContent.trim() }},
                                        away: {{ odds: oddsElements[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[SNOOKER] Set next frame: home=${{oddsElements[0].textContent.trim()}}, away=${{oddsElements[1].textContent.trim()}}`);
                                }}
                            }}
                        }});
                    }} else {{
                        console.log('[SNOOKER] No market group found for snooker');
                    }}
                }}
                // BASKETBALL (B18): Dedicated extraction logic
                else if (SPORT_CODE === 'B18') {{
                    console.log('[BASKETBALL] Starting dedicated basketball odds extraction');

                    const marketGroup = fixture.querySelector('.ovm-MarketGroup');
                    if (marketGroup) {{
                        console.log('[BASKETBALL] Found market group for basketball');

                        // Get all market elements
                        const marketElements = marketGroup.querySelectorAll('.ovm-Market');
                        console.log(`[BASKETBALL] Found ${{marketElements.length}} market elements`);

                        marketElements.forEach((market, marketIndex) => {{
                            console.log(`[BASKETBALL] Processing market ${{marketIndex + 1}}`);

                            if (marketIndex === 0) {{
                                // First market: Spread
                                const spreadParticipants = market.querySelectorAll('.ovm-ParticipantStackedCentered');
                                console.log(`[BASKETBALL] Spread participants found: ${{spreadParticipants.length}}`);

                                if (spreadParticipants.length >= 2) {{
                                    const homeHandicap = spreadParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim() || '';
                                    const homeOdds = spreadParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';
                                    const awayHandicap = spreadParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim() || '';
                                    const awayOdds = spreadParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';

                                    if (homeOdds && awayOdds) {{
                                        matchData.markets.spread = {{
                                            home: {{ line: homeHandicap, odds: homeOdds }},
                                            away: {{ line: awayHandicap, odds: awayOdds }}
                                        }};
                                        matchData.has_odds = true;
                                        results.summary.total_odds += 2;
                                        console.log(`[BASKETBALL] Set spread: home=${{homeHandicap}}@${{homeOdds}}, away=${{awayHandicap}}@${{awayOdds}}`);
                                    }}
                                }}
                            }} else if (marketIndex === 1) {{
                                // Second market: Total
                                const totalParticipants = market.querySelectorAll('.ovm-ParticipantStackedCentered');
                                console.log(`[BASKETBALL] Total participants found: ${{totalParticipants.length}}`);

                                if (totalParticipants.length >= 2) {{
                                    const overLine = totalParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim()?.replace('O', '').trim() || '';
                                    const overOdds = totalParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';
                                    const underLine = totalParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim()?.replace('U', '').trim() || '';
                                    const underOdds = totalParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';

                                    if (overOdds && underOdds) {{
                                        matchData.markets.total = {{
                                            over: {{ line: overLine, odds: overOdds }},
                                            under: {{ line: underLine, odds: underOdds }}
                                        }};
                                        results.summary.total_odds += 2;
                                        console.log(`[BASKETBALL] Set total: over=${{overLine}}@${{overOdds}}, under=${{underLine}}@${{underOdds}}`);
                                    }}
                                }}
                            }} else if (marketIndex === 2) {{
                                // Third market: Moneyline
                                const moneylineParticipants = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[BASKETBALL] Moneyline odds found: ${{moneylineParticipants.length}}`);

                                if (moneylineParticipants.length >= 2) {{
                                    if (!matchData.markets.moneyline) {{
                                        matchData.markets.moneyline = {{}};
                                    }}
                                    matchData.markets.moneyline.home = {{ odds: moneylineParticipants[0].textContent.trim() }};
                                    matchData.markets.moneyline.away = {{ odds: moneylineParticipants[1].textContent.trim() }};
                                    results.summary.total_odds += 2;
                                    console.log(`[BASKETBALL] Set moneyline: home=${{moneylineParticipants[0].textContent.trim()}}, away=${{moneylineParticipants[1].textContent.trim()}}`);
                                }}
                            }}
                        }});
                    }} else {{
                        console.log('[BASKETBALL] No market group found for basketball');
                    }}
                }}
                // BASEBALL (B16): Dedicated extraction logic
                else if (SPORT_CODE === 'B16') {{
                    console.log('[BASEBALL] Starting dedicated baseball odds extraction');

                    const marketGroup = fixture.querySelector('.ovm-MarketGroup');
                    if (marketGroup) {{
                        console.log('[BASEBALL] Found market group for baseball');

                        // Get all market elements
                        const marketElements = marketGroup.querySelectorAll('.ovm-Market');
                        console.log(`[BASEBALL] Found ${{marketElements.length}} market elements`);

                        marketElements.forEach((market, marketIndex) => {{
                            console.log(`[BASEBALL] Processing market ${{marketIndex + 1}}`);

                            if (marketIndex === 0) {{
                                // First market: Spread
                                const spreadParticipants = market.querySelectorAll('.ovm-ParticipantStackedCentered');
                                console.log(`[BASEBALL] Spread participants found: ${{spreadParticipants.length}}`);

                                if (spreadParticipants.length >= 2) {{
                                    const homeHandicap = spreadParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim() || '';
                                    const homeOdds = spreadParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';
                                    const awayHandicap = spreadParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim() || '';
                                    const awayOdds = spreadParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';

                                    if (homeOdds && awayOdds) {{
                                        matchData.markets.spread = {{
                                            home: {{ line: homeHandicap, odds: homeOdds }},
                                            away: {{ line: awayHandicap, odds: awayOdds }}
                                        }};
                                        matchData.has_odds = true;
                                        results.summary.total_odds += 2;
                                        console.log(`[BASEBALL] Set spread: home=${{homeHandicap}}@${{homeOdds}}, away=${{awayHandicap}}@${{awayOdds}}`);
                                    }}
                                }}
                            }} else if (marketIndex === 1) {{
                                // Second market: Total
                                const totalParticipants = market.querySelectorAll('.ovm-ParticipantStackedCentered');
                                console.log(`[BASEBALL] Total participants found: ${{totalParticipants.length}}`);

                                if (totalParticipants.length >= 2) {{
                                    const overLine = totalParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim()?.replace('O', '').trim() || '';
                                    const overOdds = totalParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';
                                    const underLine = totalParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim()?.replace('U', '').trim() || '';
                                    const underOdds = totalParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';

                                    if (overOdds && underOdds) {{
                                        matchData.markets.total = {{
                                            over: {{ line: overLine, odds: overOdds }},
                                            under: {{ line: underLine, odds: underOdds }}
                                        }};
                                        results.summary.total_odds += 2;
                                        console.log(`[BASEBALL] Set total: over=${{overLine}}@${{overOdds}}, under=${{underLine}}@${{underOdds}}`);
                                    }}
                                }}
                            }} else if (marketIndex === 2) {{
                                // Third market: Moneyline
                                const moneylineParticipants = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[BASEBALL] Moneyline odds found: ${{moneylineParticipants.length}}`);

                                if (moneylineParticipants.length >= 2) {{
                                    if (!matchData.markets.moneyline) {{
                                        matchData.markets.moneyline = {{}};
                                    }}
                                    matchData.markets.moneyline.home = {{ odds: moneylineParticipants[0].textContent.trim() }};
                                    matchData.markets.moneyline.away = {{ odds: moneylineParticipants[1].textContent.trim() }};
                                    results.summary.total_odds += 2;
                                    console.log(`[BASEBALL] Set moneyline: home=${{moneylineParticipants[0].textContent.trim()}}, away=${{moneylineParticipants[1].textContent.trim()}}`);
                                }}
                            }}
                        }});
                    }} else {{
                        console.log('[BASEBALL] No market group found for baseball');
                    }}
                }}
                // TABLE TENNIS (B92): Dedicated extraction logic
                else if (SPORT_CODE === 'B92') {{
                    console.log('[TABLE TENNIS] Starting dedicated table tennis odds extraction');

                    const marketGroup = fixture.querySelector('.ovm-MarketGroup');
                    if (marketGroup) {{
                        console.log('[TABLE TENNIS] Found market group for table tennis');

                        // Get all market elements
                        const marketElements = marketGroup.querySelectorAll('.ovm-Market');
                        console.log(`[TABLE TENNIS] Found ${{marketElements.length}} market elements`);

                        marketElements.forEach((market, marketIndex) => {{
                            console.log(`[TABLE TENNIS] Processing market ${{marketIndex + 1}}`);

                            if (marketIndex === 0) {{
                                // First market: Money
                                const moneyParticipants = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[TABLE TENNIS] Money odds found: ${{moneyParticipants.length}}`);

                                if (moneyParticipants.length >= 2) {{
                                    if (!matchData.markets.moneyline) {{
                                        matchData.markets.moneyline = {{}};
                                    }}
                                    matchData.markets.moneyline.home = {{ odds: moneyParticipants[0].textContent.trim() }};
                                    matchData.markets.moneyline.away = {{ odds: moneyParticipants[1].textContent.trim() }};
                                    matchData.has_odds = true;
                                    results.summary.total_odds += 2;
                                    console.log(`[TABLE TENNIS] Set moneyline: home=${{moneyParticipants[0].textContent.trim()}}, away=${{moneyParticipants[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 1) {{
                                // Second market: Game
                                const gameParticipants = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                console.log(`[TABLE TENNIS] Game odds found: ${{gameParticipants.length}}`);

                                if (gameParticipants.length >= 2) {{
                                    matchData.markets.handicap = {{
                                        home: {{ odds: gameParticipants[0].textContent.trim() }},
                                        away: {{ odds: gameParticipants[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[TABLE TENNIS] Set game handicap: home=${{gameParticipants[0].textContent.trim()}}, away=${{gameParticipants[1].textContent.trim()}}`);
                                }}
                            }} else if (marketIndex === 2) {{
                                // Third market: Game Total
                                const totalParticipants = market.querySelectorAll('.ovm-ParticipantStackedCentered_Odds');
                                const totalLines = market.querySelectorAll('.ovm-ParticipantStackedCentered_Handicap');
                                console.log(`[TABLE TENNIS] Game Total odds: ${{totalParticipants.length}}, lines: ${{totalLines.length}}`);

                                if (totalParticipants.length >= 2 && totalLines.length >= 2) {{
                                    const overLine = totalLines[0].textContent.trim().replace('O', '').replace('U', '').trim();
                                    const underLine = totalLines[1].textContent.trim().replace('O', '').replace('U', '').trim();

                                    matchData.markets.total = {{
                                        over: {{ line: overLine, odds: totalParticipants[0].textContent.trim() }},
                                        under: {{ line: underLine, odds: totalParticipants[1].textContent.trim() }}
                                    }};
                                    results.summary.total_odds += 2;
                                    console.log(`[TABLE TENNIS] Set game total: over=${{overLine}}@${{totalParticipants[0].textContent.trim()}}, under=${{underLine}}@${{totalParticipants[1].textContent.trim()}}`);
                                }}
                            }}
                        }});
                    }} else {{
                        console.log('[TABLE TENNIS] No market group found for table tennis');
                    }}
                }}
                // ESPORTS (B151): Dedicated extraction logic
                else if (SPORT_CODE === 'B151') {{
                    console.log('[ESPORTS] Starting dedicated esports odds extraction');

                    const marketGroup = fixture.querySelector('.ovm-MarketGroupEsports');
                    if (marketGroup) {{
                        console.log('[ESPORTS] Found esports market group');

                        // Check for horizontal market structure (3-way moneyline)
                        const horizontalMarket = marketGroup.querySelector('.ovm-HorizontalMarket');
                        if (horizontalMarket) {{
                            console.log('[ESPORTS] Found horizontal market structure');

                            const participants = horizontalMarket.querySelectorAll('.ovm-HorizontalMarket_Participant');
                            console.log(`[ESPORTS] Found ${{participants.length}} horizontal participants`);

                            if (participants.length >= 3) {{
                                const odds = [];
                                participants.forEach(participant => {{
                                    const oddsEl = participant.querySelector('.ovm-ParticipantOddsOnly_Odds');
                                    if (oddsEl) {{
                                        odds.push(oddsEl.textContent.trim());
                                    }}
                                }});

                                console.log('[ESPORTS] Horizontal odds found:', odds);

                                // Esports 3-way (Home | Tie | Away)
                                if (odds.length >= 3) {{
                                    matchData.markets.moneyline = {{
                                        home: {{ odds: odds[0] }},
                                        tie: {{ odds: odds[1] }},
                                        away: {{ odds: odds[2] }}
                                    }};
                                    matchData.has_odds = true;
                                    results.summary.total_odds += 3;
                                    console.log(`[ESPORTS] Set 3-way moneyline: home=${{odds[0]}}, tie=${{odds[1]}}, away=${{odds[2]}}`);
                                }}
                            }}
                        }} else {{
                            // Check for traditional market structure (basketball-style)
                            const marketElements = marketGroup.querySelectorAll('.ovm-Market');
                            console.log(`[ESPORTS] Found ${{marketElements.length}} traditional market elements`);

                            marketElements.forEach((market, marketIndex) => {{
                                console.log(`[ESPORTS] Processing market ${{marketIndex + 1}}`);

                                if (marketIndex === 0) {{
                                    // First market: Spread
                                    const spreadParticipants = market.querySelectorAll('.ovm-ParticipantStackedCentered');
                                    console.log(`[ESPORTS] Spread participants found: ${{spreadParticipants.length}}`);

                                    if (spreadParticipants.length >= 2) {{
                                        const homeHandicap = spreadParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim() || '';
                                        const homeOdds = spreadParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';
                                        const awayHandicap = spreadParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim() || '';
                                        const awayOdds = spreadParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';

                                        if (homeOdds && awayOdds) {{
                                            matchData.markets.spread = {{
                                                home: {{ line: homeHandicap, odds: homeOdds }},
                                                away: {{ line: awayHandicap, odds: awayOdds }}
                                            }};
                                            matchData.has_odds = true;
                                            results.summary.total_odds += 2;
                                            console.log(`[ESPORTS] Set spread: home=${{homeHandicap}}@${{homeOdds}}, away=${{awayHandicap}}@${{awayOdds}}`);
                                        }}
                                    }}
                                }} else if (marketIndex === 1) {{
                                    // Second market: Total
                                    const totalParticipants = market.querySelectorAll('.ovm-ParticipantStackedCentered');
                                    console.log(`[ESPORTS] Total participants found: ${{totalParticipants.length}}`);

                                    if (totalParticipants.length >= 2) {{
                                        const overLine = totalParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim()?.replace('O', '').trim() || '';
                                        const overOdds = totalParticipants[0].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';
                                        const underLine = totalParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Handicap')?.textContent?.trim()?.replace('U', '').trim() || '';
                                        const underOdds = totalParticipants[1].querySelector('.ovm-ParticipantStackedCentered_Odds')?.textContent?.trim() || '';

                                        if (overOdds && underOdds) {{
                                            matchData.markets.total = {{
                                                over: {{ line: overLine, odds: overOdds }},
                                                under: {{ line: underLine, odds: underOdds }}
                                            }};
                                            results.summary.total_odds += 2;
                                            console.log(`[ESPORTS] Set total: over=${{overLine}}@${{overOdds}}, under=${{underLine}}@${{underOdds}}`);
                                        }}
                                    }}
                                }} else if (marketIndex === 2) {{
                                    // Third market: Moneyline
                                    const moneylineParticipants = market.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                                    console.log(`[ESPORTS] Moneyline odds found: ${{moneylineParticipants.length}}`);

                                    if (moneylineParticipants.length >= 2) {{
                                        if (!matchData.markets.moneyline) {{
                                            matchData.markets.moneyline = {{}};
                                        }}
                                        matchData.markets.moneyline.home = {{ odds: moneylineParticipants[0].textContent.trim() }};
                                        matchData.markets.moneyline.away = {{ odds: moneylineParticipants[1].textContent.trim() }};
                                        results.summary.total_odds += 2;
                                        console.log(`[ESPORTS] Set moneyline: home=${{moneylineParticipants[0].textContent.trim()}}, away=${{moneylineParticipants[1].textContent.trim()}}`);
                                    }}
                                }}
                            }});
                        }}
                    }} else {{
                        console.log('[ESPORTS] No esports market group found');
                    }}
                }}
                // STANDARD: Uses market group structure for all other sports
                else {{
                    console.log('[ODDS] Using standard market extraction for sport:', SPORT_CODE);

                    // Try multiple market group selectors
                    let marketGroup = fixture.querySelector('.ovm-MarketGroup');

                    // If no market group, try alternative selectors
                    if (!marketGroup) {{
                        const alternativeSelectors = [
                            '.ovm-Fixture_Markets',
                            '.ovm-MarketGroupContainer',
                            '[class*="MarketGroup"]',
                            '.ovm-FixtureMarketGroup',
                            '.ovm-FixtureMarkets',
                            '[data-testid*="markets"]',
                            '.markets-container'
                        ];

                        for (const selector of alternativeSelectors) {{
                            marketGroup = fixture.querySelector(selector);
                            if (marketGroup) {{
                                console.log(`[ODDS] Found market group using alternative selector: ${{selector}}`);
                                break;
                            }}
                        }}

                        // DIRECT APPROACH: Look for participant elements directly in the fixture
                        if (!marketGroup) {{
                            const directParticipants = fixture.querySelectorAll('.gl-Participant_General, .ovm-ParticipantStackedCentered, .ovm-ParticipantOddsOnly');
                            if (directParticipants.length > 0) {{
                                console.log(`[ODDS] Found ${{directParticipants.length}} participant elements directly in fixture`);
                                // Create a virtual market group from these elements
                                marketGroup = fixture; // Use the fixture itself as the container
                            }}
                        }}
                    }}

                    console.log(`[ODDS] Market group found: ${{marketGroup ? 'YES' : 'NO'}}`);
                    if (marketGroup) {{
                        console.log(`[ODDS] Market group class: ${{marketGroup.className}}`);
                    }}

                    if (!marketGroup) {{
                        console.log('[ODDS] No market group found with any selector');
                        results.debug.selectors_tried.push('ODDS:NoMarketGroup');
                        results.debug.market_debug.push('No market group found');

                        // DEBUG: Try to find any market-related elements
                        const allMarketElements = fixture.querySelectorAll('[class*="arket"], [class*="dds"]');
                        console.log(`[ODDS] Found ${{allMarketElements.length}} market/odds elements in fixture`);
                        allMarketElements.forEach((el, i) => {{
                            if (i < 5) {{ // Log first 5
                                console.log(`  Element ${{i}}: ${{el.className}} - ${{el.textContent.substring(0, 50)}}...`);
                            }}
                        }});
                        results.debug.market_debug.push(`Found ${{allMarketElements.length}} market/odds elements in fixture`);
                    }} else {{
                        results.debug.market_debug.push(`Found market group: ${{marketGroup.className}}`);

                        // CHECK FOR HORIZONTAL MARKET STRUCTURE (used by soccer and other sports)
                        const horizontalMarket = marketGroup.querySelector('.ovm-HorizontalMarket');
                        if (horizontalMarket) {{
                            console.log('[ODDS] Found horizontal market structure');
                            results.debug.market_debug.push('Found horizontal market structure');

                            const participants = horizontalMarket.querySelectorAll('.ovm-HorizontalMarket_Participant');
                            console.log(`[ODDS] Found ${{participants.length}} horizontal participants`);

                            if (participants.length >= 2) {{
                                const odds = [];
                                participants.forEach(participant => {{
                                    const oddsEl = participant.querySelector('.ovm-ParticipantOddsOnly_Odds');
                                    if (oddsEl) {{
                                        const oddsText = oddsEl.textContent.trim();
                                        if (oddsText && !oddsText.includes('SP') && !oddsText.includes('Suspended')) {{
                                            odds.push(oddsText);
                                        }}
                                    }}
                                }});

                                console.log('[ODDS] Horizontal odds found:', odds);
                                results.debug.market_debug.push(`Horizontal odds found: ${{odds.join(', ')}}`);

                                // Assign to moneyline based on layout
                                if (LAYOUT.columns.includes('home') || LAYOUT.columns.includes('tie') || LAYOUT.columns.includes('away')) {{
                                    // Soccer 3-way
                                    if (odds.length >= 3) {{
                                        matchData.markets.moneyline = {{
                                            home: {{ odds: odds[0] }},
                                            tie: {{ odds: odds[1] }},
                                            away: {{ odds: odds[2] }}
                                        }};
                                        results.summary.total_odds += 3;
                                    }} else if (odds.length >= 2) {{
                                        matchData.markets.moneyline = {{
                                            home: {{ odds: odds[0] }},
                                            away: {{ odds: odds[1] }}
                                        }};
                                        results.summary.total_odds += 2;
                                    }}
                                }} else {{
                                    // Standard 2-way
                                    if (odds.length >= 2) {{
                                        matchData.markets.moneyline = {{
                                            home: {{ odds: odds[0] }},
                                            away: {{ odds: odds[1] }}
                                        }};
                                        results.summary.total_odds += 2;
                                    }}
                                }}
                            }}
                        }} else {{
                            // Try traditional market structure
                            let marketElements = marketGroup.querySelectorAll('.ovm-Market');
                            console.log(`[ODDS] Found ${{marketElements.length}} .ovm-Market elements`);
                            results.debug.market_debug.push(`Found ${{marketElements.length}} .ovm-Market elements`);

                            if (marketElements.length === 0) {{
                                // Try alternative market selectors
                                const marketSelectors = [
                                    '[class*="Market"]',
                                    '.market-item',
                                    '.ovm-MarketItem',
                                    '[data-market]',
                                    '.market-container'
                                ];

                                for (const selector of marketSelectors) {{
                                    marketElements = marketGroup.querySelectorAll(selector);
                                    if (marketElements.length > 0) {{
                                        console.log(`[ODDS] Found ${{marketElements.length}} markets using selector: ${{selector}}`);
                                        results.debug.market_debug.push(`Found ${{marketElements.length}} markets using selector: ${{selector}}`);
                                        break;
                                    }}
                                }}

                                if (marketElements.length === 0) {{
                                    // DIRECT ODDS EXTRACTION: Look for odds directly in the fixture
                                    console.log('[ODDS] No market elements found, trying direct odds extraction');
                                    const directOddsSelectors = [
                                        '.ovm-ParticipantOddsOnly_Odds',
                                        '[class*="Odds"]',
                                        '.gl-Participant span',
                                        '.ovm-ParticipantOddsOnly span',
                                        '.ovm-ParticipantOddsOnly',
                                        '.ovm-ParticipantCentered [class*="Odds"]',
                                        '.ovm-ParticipantStackedCentered_Odds'
                                    ];

                                    let allOdds = [];
                                    for (const selector of directOddsSelectors) {{
                                        const oddsElements = fixture.querySelectorAll(selector);
                                        if (oddsElements.length > 0) {{
                                            console.log(`[ODDS] Found ${{oddsElements.length}} odds using direct selector: ${{selector}}`);
                                            oddsElements.forEach(el => {{
                                                const oddsText = el.textContent ? el.textContent.trim() : '';
                                                if (oddsText && !oddsText.includes('SP') && !oddsText.includes('Suspended') && !oddsText.includes('suspended')) {{
                                                    allOdds.push(oddsText);
                                                }}
                                            }});
                                        }}
                                    }}

                                    if (allOdds.length >= 2) {{
                                        console.log('[ODDS] Direct odds found:', allOdds);
                                        results.debug.market_debug.push(`Direct odds found: ${{allOdds.join(', ')}}`);

                                        // Assign to moneyline based on layout
                                        if (LAYOUT.columns.includes('home') || LAYOUT.columns.includes('tie') || LAYOUT.columns.includes('away')) {{
                                            // Soccer 3-way
                                            if (allOdds.length >= 3) {{
                                                matchData.markets.moneyline = {{
                                                    home: {{ odds: allOdds[0] }},
                                                    tie: {{ odds: allOdds[1] }},
                                                    away: {{ odds: allOdds[2] }}
                                                }};
                                                results.summary.total_odds += 3;
                                            }} else if (allOdds.length >= 2) {{
                                                matchData.markets.moneyline = {{
                                                    home: {{ odds: allOdds[0] }},
                                                    away: {{ odds: allOdds[1] }}
                                                }};
                                                results.summary.total_odds += 2;
                                            }}
                                        }} else {{
                                            // Standard 2-way
                                            if (allOdds.length >= 2) {{
                                                matchData.markets.moneyline = {{
                                                    home: {{ odds: allOdds[0] }},
                                                    away: {{ odds: allOdds[1] }}
                                                }};
                                                results.summary.total_odds += 2;
                                            }}
                                        }}
                                    }} else {{
                                        // Log all elements in market group for debugging
                                        const allElements = marketGroup.querySelectorAll('*');
                                        console.log(`[ODDS] Market group contains ${{allElements.length}} total elements`);
                                        results.debug.market_debug.push(`Market group contains ${{allElements.length}} total elements`);

                                        const uniqueClasses = new Set();
                                        allElements.forEach(el => {{
                                            if (el.className && typeof el.className === 'string') {{
                                                el.className.split(' ').forEach(cls => {{
                                                    if (cls.includes('arket') || cls.includes('dds') || cls.includes('articipant')) {{
                                                        uniqueClasses.add(cls);
                                                    }}
                                                }});
                                            }}
                                        }});
                                        console.log('[ODDS] Classes containing market/odds/participant:', Array.from(uniqueClasses));
                                        results.debug.market_debug.push(`Classes containing market/odds/participant: ${{Array.from(uniqueClasses).join(', ')}}`);
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}

                // Process traditional market elements if found
                let marketElements = [];
                if (marketGroup) {{
                    marketElements = marketGroup.querySelectorAll('.ovm-Market');
                }}

                if (marketElements && marketElements.length > 0) {{
                    console.log(`[ODDS] Processing ${{marketElements.length}} traditional market elements`);
                    marketElements.forEach((market, marketIndex) => {{
                        console.log(`[MARKET ${{marketIndex + 1}}] Processing market element, class: ${{market.className}}`);
                        const marketType = LAYOUT.columns[marketIndex];
                        if (!marketType) {{
                            console.log(`[MARKET ${{marketIndex + 1}}] No mapping for index ${{marketIndex}}`);
                            return;
                        }}

                        console.log(`[MARKET ${{marketIndex + 1}}] Type: ${{marketType}}`);

                        // Check for blank markets
                        const blanks = market.querySelectorAll('.ovm-Market_Blank');
                        if (blanks.length === 2) {{
                            console.log(`[MARKET ${{marketIndex + 1}}] Blank/unavailable`);
                            return;
                        }}

                        // Log market structure for debugging
                        console.log(`[MARKET ${{marketIndex + 1}}] HTML structure:`, market.outerHTML.substring(0, 200) + '...');

                        // Extract ParticipantStackedCentered (handicap + odds)
                        const stackedParticipants = market.querySelectorAll('.ovm-ParticipantStackedCentered');

                        if (stackedParticipants.length > 0) {{
                            console.log(`[MARKET ${{marketIndex + 1}}] Found ${{stackedParticipants.length}} stacked participants`);

                            const participants = [];
                            stackedParticipants.forEach((participant, i) => {{
                                const handicapEl = participant.querySelector('.ovm-ParticipantStackedCentered_Handicap');
                                const oddsEl = participant.querySelector('.ovm-ParticipantStackedCentered_Odds');

                                if (handicapEl && oddsEl) {{
                                    const handicap = handicapEl.textContent.trim();
                                    const odds = oddsEl.textContent.trim();
                                    participants.push({{ handicap, odds }});
                                    console.log(`  Participant ${{i + 1}}: "${{handicap}}" "${{odds}}"`);
                                }}
                            }});

                            // Assign to appropriate market based on type
                            if (marketType === 'spread' && participants.length >= 2) {{
                                matchData.markets.spread = {{
                                    home: {{ line: participants[0].handicap, odds: participants[0].odds }},
                                    away: {{ line: participants[1].handicap, odds: participants[1].odds }}
                                }};
                                results.summary.total_odds += 2;
                            }} else if (marketType === 'total' && participants.length >= 2) {{
                                // Parse line from "O 39.5" or "U 39.5"
                                const overLine = participants[0].handicap.match(/([\\d.]+)/)?.[1] || participants[0].handicap;
                                const underLine = participants[1].handicap.match(/([\\d.]+)/)?.[1] || participants[1].handicap;

                                matchData.markets.total = {{
                                    over: {{ line: overLine, odds: participants[0].odds }},
                                    under: {{ line: underLine, odds: participants[1].odds }}
                                }};
                                results.summary.total_odds += 2;
                            }} else if ((marketType === 'moneyline' || marketType === 'match' || marketType === 'game') && participants.length >= 2) {{
                                matchData.markets.moneyline = {{
                                    home: {{ odds: participants[0].odds }},
                                    away: {{ odds: participants[1].odds }}
                                }};
                                results.summary.total_odds += 2;
                            }}
                        }}


                        // Extract ParticipantOddsOnly (just odds, no handicaps)
                        const oddsOnlyParticipants = market.querySelectorAll('.ovm-ParticipantOddsOnly:not(.ovm-ParticipantOddsOnly_Suspended)');

                        if (oddsOnlyParticipants.length > 0) {{
                            console.log(`[MARKET ${{marketIndex + 1}}] Found ${{oddsOnlyParticipants.length}} odds-only participants`);

                            const participants = [];
                            oddsOnlyParticipants.forEach((participant, i) => {{
                                const oddsEl = participant.querySelector('.ovm-ParticipantOddsOnly_Odds');
                                if (oddsEl) {{
                                    const odds = oddsEl.textContent.trim();
                                    participants.push({{ odds }});
                                    console.log(`  Participant ${{i + 1}}: "${{odds}}"`);
                                }}
                            }});

                            if ((marketType === 'moneyline' || marketType === 'match') && participants.length >= 2) {{
                                if (!matchData.markets.moneyline) {{
                                    matchData.markets.moneyline = {{}};
                                }}
                                matchData.markets.moneyline.home = {{ odds: participants[0].odds }};
                                matchData.markets.moneyline.away = {{ odds: participants[1].odds }};
                                results.summary.total_odds += 2;
                            }} else if (marketType === 'moneyline' && participants.length === 1) {{
                                if (!matchData.markets.moneyline) {{
                                    matchData.markets.moneyline = {{}};
                                }}
                                matchData.markets.moneyline.home = {{ odds: participants[0].odds }};
                                results.summary.total_odds += 1;
                            }}
                        }}

                        // Extract ParticipantOddsOnly (just odds, no handicaps) - for all sports
                        const oddsOnlyParticipants2 = market.querySelectorAll('.ovm-ParticipantOddsOnly:not(.ovm-ParticipantOddsOnly_Suspended)');

                        if (oddsOnlyParticipants2.length > 0) {{
                            console.log(`[MARKET ${{marketIndex + 1}}] Found ${{oddsOnlyParticipants2.length}} odds-only participants`);

                            const participants = [];
                            oddsOnlyParticipants2.forEach((participant, i) => {{
                                const oddsEl = participant.querySelector('.ovm-ParticipantOddsOnly_Odds');
                                if (oddsEl) {{
                                    const odds = oddsEl.textContent.trim();
                                    participants.push({{ odds }});
                                    console.log(`  Participant ${{i + 1}}: "${{odds}}"`);
                                }}
                            }});

                            if ((marketType === 'moneyline' || marketType === 'match') && participants.length >= 2) {{
                                if (!matchData.markets.moneyline) {{
                                    matchData.markets.moneyline = {{}};
                                }}
                                matchData.markets.moneyline.home = {{ odds: participants[0].odds }};
                                matchData.markets.moneyline.away = {{ odds: participants[1].odds }};
                                results.summary.total_odds += 2;
                            }} else if (marketType === 'moneyline' && participants.length === 1) {{
                                if (!matchData.markets.moneyline) {{
                                    matchData.markets.moneyline = {{}};
                                }}
                                matchData.markets.moneyline.home = {{ odds: participants[0].odds }};
                                results.summary.total_odds += 1;
                            }}
                        }}

                        // Add debug logging for market group detection
                        console.log(`[ODDS] Market group found: ${{marketGroup ? 'YES' : 'NO'}}`);
                        if (marketGroup) {{
                            console.log(`[ODDS] Market group class: ${{marketGroup.className}}`);
                            console.log(`[ODDS] Market group HTML: ${{marketGroup.outerHTML.substring(0, 200)}}...`);
    
                            // Check for markets within the market group
                            const marketsInGroup = marketGroup.querySelectorAll('.ovm-Market');
                            console.log(`[ODDS] Found ${{marketsInGroup.length}} .ovm-Market elements in market group`);
                        }} else {{
                            // If no market group found, try to find odds directly in the fixture
                            console.log(`[ODDS] No market group found, trying direct odds extraction from fixture`);
                            const directOdds = fixture.querySelectorAll('.ovm-ParticipantOddsOnly_Odds');
                            console.log(`[ODDS] Found ${{directOdds.length}} direct odds elements in fixture`);
                            directOdds.forEach((el, i) => {{
                                if (i < 5) {{ // Log first 5
                                    console.log(`  Direct odds ${{i}}: "${{el.textContent.trim()}}"`);
                                }}
                            }});
    
                            if (directOdds.length >= 2) {{
                                if (!matchData.markets.moneyline) {{
                                    matchData.markets.moneyline = {{}};
                                }}
                                matchData.markets.moneyline.home = {{ odds: directOdds[0].textContent.trim() }};
                                matchData.markets.moneyline.away = {{ odds: directOdds[1].textContent.trim() }};
                                matchData.has_odds = true;
                                results.summary.total_odds += 2;
                                console.log(`[ODDS] Set moneyline from direct odds: home=${{directOdds[0].textContent.trim()}}, away=${{directOdds[1].textContent.trim()}}`);
                            }}
                        }}

                        // Soccer 3-way moneyline (Home | Tie | Away)
                        if ((marketType === 'home' || marketType === 'tie' || marketType === 'away') && !matchData.markets.moneyline) {{
                            const centeredParticipants = market.querySelectorAll('.ovm-ParticipantCentered');

                            if (centeredParticipants.length >= 3) {{
                                console.log(`[MARKET ${{marketIndex + 1}}] Found ${{centeredParticipants.length}} centered participants (3-way)`);

                                matchData.markets.moneyline = {{}};

                                const homeOddsEl = centeredParticipants[0].querySelector('[class*="Odds"]');
                                const tieOddsEl = centeredParticipants[1].querySelector('[class*="Odds"]');
                                const awayOddsEl = centeredParticipants[2].querySelector('[class*="Odds"]');

                                if (homeOddsEl) {{
                                    matchData.markets.moneyline.home = {{ odds: homeOddsEl.textContent.trim() }};
                                    results.summary.total_odds += 1;
                                }}
                                if (tieOddsEl) {{
                                    matchData.markets.moneyline.tie = {{ odds: tieOddsEl.textContent.trim() }};
                                    results.summary.total_odds += 1;
                                }}
                                if (awayOddsEl) {{
                                    matchData.markets.moneyline.away = {{ odds: awayOddsEl.textContent.trim() }};
                                    results.summary.total_odds += 1;
                                }}
                            }}
                        }}

                        // Check for suspended markets
                        const suspended = market.querySelector('.ovm-ParticipantOddsOnly_Suspended');
                        if (suspended) {{
                            console.log(`[MARKET ${{marketIndex + 1}}] Market suspended`);
                        }}
                    }});

                    results.summary.total_markets += Object.keys(matchData.markets).length;
                    console.log('[ODDS] Extracted markets:', Object.keys(matchData.markets));
                }}

            }} catch (e) {{
                console.log('[ODDS] Error:', e.message);
            }}
            
            // ==========================================
            // 5. VALIDATION AND ADD TO RESULTS
            // ==========================================
            const hasTeams = matchData.teams.home && matchData.teams.away;
            const hasValidTeams = matchData.teams.home.length > 2 && matchData.teams.away.length > 2;
            const hasOdds = Object.keys(matchData.markets).length > 0;

            // INTELLIGENT SPORT DETECTION: Analyze team names to detect actual sport
            let detectedSport = CURRENT_SPORT_NAME;
            let sportConfidence = 0;
            const sportDetectionReasoning = [];

            // FIRST: Check if this is a redirected page by looking at URL vs expected sport
            const currentUrl = window.location.href;
            const isRedirected = !currentUrl.includes('/IP/' + SPORT_CODE + '/');

            if (isRedirected) {{
                // If redirected, determine what sport actually has live matches
                const redirectMappings = {{
                    'B16': 'Baseball',    // Baseball redirects to Baseball (fixed)
                    'B18': 'Basketball',  // Basketball redirects to Basketball (fixed)
                    'B1': 'Soccer',       // Soccer redirects to Soccer (fixed)
                    'B3': 'Cricket',      // Cricket redirects to Cricket (fixed)
                    'B13': 'Tennis',      // Tennis redirects to Tennis (fixed)
                    'B91': 'Volleyball',  // Volleyball redirects to Volleyball (fixed)
                    'B92': 'Table Tennis', // Table Tennis redirects to Table Tennis (fixed)
                    'B94': 'Badminton'    // Badminton redirects to Badminton (fixed)
                }};

                if (redirectMappings[SPORT_CODE]) {{
                    detectedSport = redirectMappings[SPORT_CODE];
                    sportConfidence = 100; // High confidence for redirected pages
                    sportDetectionReasoning.push(`REDIRECTED: ${{SPORT_CODE}} -> ${{detectedSport}}`);
                }}
            }} else {{
                // Not redirected, use team name analysis
                if (hasTeams && hasValidTeams) {{
                    const combinedTeamNames = (matchData.teams.home + ' ' + matchData.teams.away).toLowerCase();

                    // Sport detection patterns (same as Python logic)
                    const sportPatterns = {{
                        'Basketball': [
                            /lakers|celtics|warriors|bulls|heat|knicks|nets|76ers|raptors|bucks|cavaliers|pistons|hawks|hornets|wizards|magic|thunder|jazz|kings|clippers|mavericks|spurs|pelicans|blazers|timberwolves|sun|nuggets|pacers|bulls/gi,
                            /nba|nbl|acb|phoenix|kbl/gi
                        ],
                        'Baseball': [
                            /yankees|red sox|dodgers|giants|mets|phillies|astros|rangers|angels|mariners|twins|guardians|royals|tigers|white sox|orioles|rays|blue jays|braves|nationals|marlins|pirates|cardinals|brewers|cubs|reds|diamondbacks|padres|rockies/gi,
                            /mlb|hanwha|samsung|lions|eagles/gi
                        ],
                        'Soccer': [
                            /arsenal|chelsea|liverpool|manchester|barcelona|real madrid|bayern|juventus|inter miami|lafc|la galaxy|real salt lake|fc|united|city|madrid|juventus|psg|dortmund|ac milan|napoli|roma|atalanta|lazio|inter|sampdoria|sassuolo|udinese|hellas verona|empoli|monza/gi,
                            /epl|premier league|la liga|bundesliga|serie a|mls/gi
                        ],
                        'American Football': [
                            /ravens|steelers|chiefs|patriots|eagles|vikings|packers|bears|lions|falcons|panthers|saints|buccaneers|cardinals|rams|49ers|seahawks|jets|dolphins|bills|texans|colts|titans|jaguars|browns|bengals|chargers/gi,
                            /nfl|super bowl/gi
                        ],
                        'Tennis': [
                            /vs|def|retired|walkover/gi,
                            /set|game|deuce|advantage/gi
                        ],
                        'Cricket': [
                            /division|all out|declared|follow on|innings|wickets|overs|wickets/gi,
                            /pakistan|south africa|zimbabwe|afghanistan|australia|england|india|new zealand|west indies|sri lanka|bangladesh/gi,
                            /test|odi|t20|cricket/gi
                        ]
                    }};

                    // Detect sport based on team names
                    for (const [sportName, patterns] of Object.entries(sportPatterns)) {{
                        let sportScore = 0;
                        for (const pattern of patterns) {{
                            const matches = combinedTeamNames.match(pattern);
                            if (matches) {{
                                sportScore += matches.length;
                                sportDetectionReasoning.push(`${{sportName}}: found "${{matches.join(', ')}}"`);
                            }}
                        }}

                        if (sportScore > sportConfidence) {{
                            sportConfidence = sportScore;
                            detectedSport = sportName;
                        }}
                    }}

                    // If confidence is low, keep original sport
                    if (sportConfidence < 2) {{
                        detectedSport = CURRENT_SPORT_NAME;
                        sportDetectionReasoning.push(`Low confidence (${{sportConfidence}}), keeping original sport`);
                    }} else {{
                        sportDetectionReasoning.push(`High confidence (${{sportConfidence}}), detected ${{detectedSport}}`);
                    }}
                }}
            }}

            // Update results with sport detection info
            results.debug.sport_detection.detected_sport = detectedSport;
            results.debug.sport_detection.confidence = sportConfidence;
            results.debug.sport_detection.reasoning = sportDetectionReasoning;

            // Add sport and sport_code to match data for deduplication
            matchData.sport = detectedSport;
            matchData.sport_code = SPORT_CODE;

            // Add odds availability flag
            matchData.has_odds = hasOdds;

            if (hasTeams && hasValidTeams) {{
                results.matches.push(matchData);
                results.summary.total_matches++;
                if (hasOdds) {{
                    console.log(`[FIXTURE ${{index + 1}}] Valid match with odds added: ${{matchData.teams.home}} vs ${{matchData.teams.away}}`);
                }} else {{
                    console.log(`[FIXTURE ${{index + 1}}] Valid match without odds added: ${{matchData.teams.home}} vs ${{matchData.teams.away}}`);
                }}
            }} else {{
                console.log(`[FIXTURE ${{index + 1}}] Invalid - Teams: "${{matchData.teams.home}}" vs "${{matchData.teams.away}}"`);
            }}
        }});
        
        console.log('\\n=== EXTRACTION COMPLETE ===');
        console.log(`Matches: ${{results.summary.total_matches}}`);
        console.log(`Markets: ${{results.summary.total_markets}}`);
        console.log(`Odds: ${{results.summary.total_odds}}`);
        console.log(`Sport Detection: Requested=${{results.debug.sport_detection.requested_sport}}, Detected=${{results.debug.sport_detection.detected_sport}}, Confidence=${{results.debug.sport_detection.confidence}}`);

        return results;
        
    }} catch (error) {{
        console.error('EXTRACTION ERROR:', error);
        return {{
            sport_code: '{sport_code}',
            error: error.message,
            matches: [],
            summary: {{ total_matches: 0, total_markets: 0, total_odds: 0 }}
        }};
    }}
}})();
"""


# Usage in playwright_bet365_live.py:
# extraction_script = get_comprehensive_extraction_script(
#     sport_code=sport_code,
#     sport_mappings_js=sport_mappings_js,
#     match_selectors_js=match_selectors_js,
#     team_selectors_js=team_selectors_js,
#     score_selectors_js=score_selectors_js,
#     odds_selectors_js=odds_selectors_js,
#     status_selectors_js=status_selectors_js
# )

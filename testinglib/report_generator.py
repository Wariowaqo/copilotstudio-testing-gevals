"""
Custom HTML Report Generator for Copilot Studio Agent Evaluation

Generates a modern, standalone HTML report with:
- Dark theme with gold accents (matching brand colors)
- Compact table view for quick overview
- Expandable details panel for deep dive
- Search and filtering
- Responsive design optimized for testing teams
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any
import html as html_escape


def generate_html_report(test_results: List[Dict[str, Any]], output_path: str):
    """Generate a beautiful standalone HTML report."""
    
    # Calculate summary stats
    total_tests = len(test_results)
    passed_tests = sum(1 for t in test_results if t.get('passed', False))
    failed_tests = total_tests - passed_tests
    avg_score = sum(float(t.get('overall_score', 0)) for t in test_results) / total_tests if total_tests > 0 else 0
    
    # Generate table rows HTML
    table_rows_html = ""
    for i, test in enumerate(test_results):
        score = float(test.get('overall_score', 0))
        score_class = "high" if score >= 0.70 else "medium" if score >= 0.50 else "low"
        status_class = "passed" if test.get('passed', False) else "failed"
        status_icon = "✓" if test.get('passed', False) else "✗"
        
        # Truncate question for table view
        question = test.get('input_text', '')
        question_short = question[:80] + "..." if len(question) > 80 else question
        
        # Get scores
        corr = float(test.get('correctness_score', 0))
        rel = float(test.get('relevancy_score', 0))
        coh = float(test.get('coherence_score', 0))
        comp = float(test.get('completeness_score', 0))
        
        conv_id = test.get('conversation_id', 'N/A')
        conv_id_short = conv_id[:12] + "..." if len(conv_id) > 12 else conv_id
        
        # Escape HTML in text content
        expected_escaped = html_escape.escape(test.get('expected', ''))
        actual_escaped = html_escape.escape(test.get('actual', ''))
        question_escaped = html_escape.escape(question)
        
        table_rows_html += f'''
        <tr class="test-row" data-score="{score}" data-status="{status_class}" data-index="{i}">
            <td class="col-status">
                <span class="status-badge {status_class}">{status_icon}</span>
            </td>
            <td class="col-id" title="{conv_id}">
                <code>{conv_id_short}</code>
            </td>
            <td class="col-question" title="{html_escape.escape(question)}">
                {html_escape.escape(question_short)}
            </td>
            <td class="col-score">
                <span class="score-pill {score_class}">{score:.2f}</span>
            </td>
            <td class="col-metrics">
                <div class="mini-metrics">
                    <span class="mini-metric corr" title="Correctness: {corr:.2f}">{corr:.2f}</span>
                    <span class="mini-metric rel" title="Relevancy: {rel:.2f}">{rel:.2f}</span>
                    <span class="mini-metric coh" title="Coherence: {coh:.2f}">{coh:.2f}</span>
                    <span class="mini-metric comp" title="Completeness: {comp:.2f}">{comp:.2f}</span>
                </div>
            </td>
            <td class="col-actions">
                <button class="details-btn" onclick="showDetails({i})">
                    <span>Details</span>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 18l6-6-6-6"/>
                    </svg>
                </button>
            </td>
        </tr>
        '''
    
    # Generate details data as JSON for the modal
    details_json = json.dumps([{
        "index": i,
        "passed": t.get('passed', False),
        "conversation_id": t.get('conversation_id', 'N/A'),
        "question": t.get('input_text', ''),
        "expected": t.get('expected', ''),
        "actual": t.get('actual', ''),
        "overall_score": t.get('overall_score', '0.00'),
        "correctness_score": t.get('correctness_score', '0.00'),
        "relevancy_score": t.get('relevancy_score', '0.00'),
        "coherence_score": t.get('coherence_score', '0.00'),
        "completeness_score": t.get('completeness_score', '0.00'),
        "correctness_reason": t.get('correctness_reason', ''),
        "relevancy_reason": t.get('relevancy_reason', ''),
        "coherence_reason": t.get('coherence_reason', ''),
        "completeness_reason": t.get('completeness_reason', ''),
    } for i, t in enumerate(test_results)])
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Copilot Studio Agent Evaluation Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-card: #1c2128;
            --bg-hover: #252c35;
            --accent-gold: #c9a227;
            --accent-gold-light: #d4af37;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --success: #3fb950;
            --success-bg: rgba(63, 185, 80, 0.15);
            --danger: #f85149;
            --danger-bg: rgba(248, 81, 73, 0.15);
            --warning: #d29922;
            --info: #58a6ff;
            --border: #30363d;
            --corr-color: #58a6ff;
            --rel-color: #3fb950;
            --coh-color: #d29922;
            --comp-color: #a371f7;
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.5;
        }}
        
        /* ===== HEADER ===== */
        .header {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 24px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .header-left h1 {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--accent-gold);
            margin-bottom: 4px;
        }}
        
        .header-left .subtitle {{
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}
        
        .header-right {{
            text-align: right;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        
        /* ===== STATS BAR ===== */
        .stats-bar {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 16px 32px;
            display: flex;
            gap: 32px;
        }}
        
        .stat {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .stat-value {{
            font-size: 1.75rem;
            font-weight: 700;
        }}
        
        .stat.total .stat-value {{ color: var(--accent-gold); }}
        .stat.passed .stat-value {{ color: var(--success); }}
        .stat.failed .stat-value {{ color: var(--danger); }}
        .stat.avg .stat-value {{ color: var(--info); }}
        
        .stat-label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* ===== CONTROLS ===== */
        .controls {{
            padding: 16px 32px;
            display: flex;
            gap: 16px;
            align-items: center;
            flex-wrap: wrap;
            border-bottom: 1px solid var(--border);
        }}
        
        .search-box {{
            flex: 1;
            min-width: 250px;
            max-width: 400px;
            position: relative;
        }}
        
        .search-box input {{
            width: 100%;
            padding: 10px 16px 10px 40px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-primary);
            font-size: 0.875rem;
        }}
        
        .search-box input:focus {{
            outline: none;
            border-color: var(--accent-gold);
        }}
        
        .search-box::before {{
            content: "🔍";
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.875rem;
        }}
        
        .filter-btns {{
            display: flex;
            gap: 8px;
        }}
        
        .download-btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            background: var(--accent-gold);
            border: none;
            border-radius: 8px;
            color: var(--bg-primary);
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            margin-left: 16px;
        }}
        
        .download-btn:hover {{
            background: #d4af37;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(201, 162, 39, 0.3);
        }}
        
        .download-btn svg {{
            width: 18px;
            height: 18px;
        }}
        
        .filter-btn {{
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            border: 1px solid var(--border);
            background: transparent;
            color: var(--text-secondary);
            transition: all 0.2s;
        }}
        
        .filter-btn:hover {{
            border-color: var(--accent-gold);
            color: var(--accent-gold);
        }}
        
        .filter-btn.active {{
            background: var(--accent-gold);
            border-color: var(--accent-gold);
            color: var(--bg-primary);
        }}
        
        .metrics-legend {{
            display: flex;
            gap: 16px;
            margin-left: auto;
            font-size: 0.75rem;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            color: var(--text-secondary);
        }}
        
        .legend-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}
        
        .legend-dot.corr {{ background: var(--corr-color); }}
        .legend-dot.rel {{ background: var(--rel-color); }}
        .legend-dot.coh {{ background: var(--coh-color); }}
        .legend-dot.comp {{ background: var(--comp-color); }}
        
        /* ===== TABLE ===== */
        .table-container {{
            padding: 0 32px 32px;
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}
        
        thead {{
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        
        th {{
            background: var(--bg-secondary);
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border);
        }}
        
        td {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}
        
        .test-row {{
            transition: background 0.15s;
        }}
        
        .test-row:hover {{
            background: var(--bg-hover);
        }}
        
        .col-status {{ width: 60px; text-align: center; }}
        .col-id {{ width: 120px; }}
        .col-question {{ min-width: 300px; }}
        .col-score {{ width: 80px; text-align: center; }}
        .col-metrics {{ width: 200px; }}
        .col-actions {{ width: 100px; text-align: center; }}
        
        .status-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            font-weight: 600;
            font-size: 0.875rem;
        }}
        
        .status-badge.passed {{
            background: var(--success-bg);
            color: var(--success);
        }}
        
        .status-badge.failed {{
            background: var(--danger-bg);
            color: var(--danger);
        }}
        
        .col-id code {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-muted);
            background: var(--bg-card);
            padding: 4px 8px;
            border-radius: 4px;
        }}
        
        .score-pill {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 0.8rem;
        }}
        
        .score-pill.high {{ background: var(--success-bg); color: var(--success); }}
        .score-pill.medium {{ background: rgba(210, 153, 34, 0.15); color: var(--warning); }}
        .score-pill.low {{ background: var(--danger-bg); color: var(--danger); }}
        
        .mini-metrics {{
            display: flex;
            gap: 6px;
        }}
        
        .mini-metric {{
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }}
        
        .mini-metric.corr {{ background: rgba(88, 166, 255, 0.15); color: var(--corr-color); }}
        .mini-metric.rel {{ background: rgba(63, 185, 80, 0.15); color: var(--rel-color); }}
        .mini-metric.coh {{ background: rgba(210, 153, 34, 0.15); color: var(--coh-color); }}
        .mini-metric.comp {{ background: rgba(163, 113, 247, 0.15); color: var(--comp-color); }}
        
        .details-btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 14px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-secondary);
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .details-btn:hover {{
            background: var(--accent-gold);
            border-color: var(--accent-gold);
            color: var(--bg-primary);
        }}
        
        .details-btn svg {{
            transition: transform 0.2s;
        }}
        
        .details-btn:hover svg {{
            transform: translateX(2px);
        }}
        
        /* ===== MODAL ===== */
        .modal-overlay {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.7);
            z-index: 100;
            align-items: center;
            justify-content: center;
            padding: 40px;
        }}
        
        .modal-overlay.active {{
            display: flex;
        }}
        
        .modal {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            width: 100%;
            max-width: 900px;
            max-height: 90vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        
        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            background: var(--bg-card);
        }}
        
        .modal-header h2 {{
            font-size: 1.1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .modal-status {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .modal-status.passed {{ background: var(--success-bg); color: var(--success); }}
        .modal-status.failed {{ background: var(--danger-bg); color: var(--danger); }}
        
        .modal-close {{
            width: 32px;
            height: 32px;
            border-radius: 6px;
            border: none;
            background: transparent;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 1.25rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .modal-close:hover {{
            background: var(--bg-hover);
            color: var(--text-primary);
        }}
        
        .modal-body {{
            padding: 24px;
            overflow-y: auto;
            flex: 1;
        }}
        
        .modal-meta {{
            display: flex;
            gap: 24px;
            margin-bottom: 24px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}
        
        .meta-item {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        
        .meta-label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }}
        
        .meta-value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            color: var(--text-primary);
        }}
        
        .modal-score {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .modal-score-value {{
            font-size: 1.5rem;
            font-weight: 700;
        }}
        
        .modal-score-value.high {{ color: var(--success); }}
        .modal-score-value.medium {{ color: var(--warning); }}
        .modal-score-value.low {{ color: var(--danger); }}
        
        .content-block {{
            margin-bottom: 20px;
        }}
        
        .content-block h4 {{
            font-size: 0.75rem;
            text-transform: uppercase;
            color: var(--accent-gold);
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .content-block p {{
            background: var(--bg-card);
            padding: 16px;
            border-radius: 8px;
            border: 1px solid var(--border);
            font-size: 0.9rem;
            color: var(--text-primary);
            line-height: 1.7;
            white-space: pre-wrap;
        }}
        
        .metrics-detail {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            margin-top: 24px;
        }}
        
        .metric-detail-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
            border-left: 3px solid;
        }}
        
        .metric-detail-card.corr {{ border-left-color: var(--corr-color); }}
        .metric-detail-card.rel {{ border-left-color: var(--rel-color); }}
        .metric-detail-card.coh {{ border-left-color: var(--coh-color); }}
        .metric-detail-card.comp {{ border-left-color: var(--comp-color); }}
        
        .metric-detail-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .metric-detail-name {{
            font-weight: 600;
            font-size: 0.85rem;
        }}
        
        .metric-detail-score {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 1.1rem;
        }}
        
        .metric-detail-card.corr .metric-detail-score {{ color: var(--corr-color); }}
        .metric-detail-card.rel .metric-detail-score {{ color: var(--rel-color); }}
        .metric-detail-card.coh .metric-detail-score {{ color: var(--coh-color); }}
        .metric-detail-card.comp .metric-detail-score {{ color: var(--comp-color); }}
        
        .metric-detail-bar {{
            height: 6px;
            background: var(--bg-primary);
            border-radius: 3px;
            margin-bottom: 12px;
            overflow: hidden;
        }}
        
        .metric-detail-bar-fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.4s ease;
        }}
        
        .metric-detail-card.corr .metric-detail-bar-fill {{ background: var(--corr-color); }}
        .metric-detail-card.rel .metric-detail-bar-fill {{ background: var(--rel-color); }}
        .metric-detail-card.coh .metric-detail-bar-fill {{ background: var(--coh-color); }}
        .metric-detail-card.comp .metric-detail-bar-fill {{ background: var(--comp-color); }}
        
        .metric-detail-reason {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            line-height: 1.6;
        }}
        
        .modal-nav {{
            display: flex;
            justify-content: space-between;
            padding: 16px 24px;
            border-top: 1px solid var(--border);
            background: var(--bg-card);
        }}
        
        .nav-btn {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            background: transparent;
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-secondary);
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .nav-btn:hover:not(:disabled) {{
            border-color: var(--accent-gold);
            color: var(--accent-gold);
        }}
        
        .nav-btn:disabled {{
            opacity: 0.4;
            cursor: not-allowed;
        }}
        
        /* ===== EMPTY STATE ===== */
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }}
        
        .empty-state-icon {{
            font-size: 3rem;
            margin-bottom: 16px;
        }}
        
        /* ===== RESPONSIVE ===== */
        @media (max-width: 900px) {{
            .header {{ flex-direction: column; gap: 16px; text-align: center; }}
            .stats-bar {{ flex-wrap: wrap; justify-content: center; }}
            .controls {{ flex-direction: column; }}
            .search-box {{ max-width: 100%; }}
            .metrics-legend {{ margin-left: 0; justify-content: center; }}
            .metrics-detail {{ grid-template-columns: 1fr; }}
            .modal {{ margin: 20px; max-height: calc(100vh - 40px); }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-left">
            <h1>🤖 Copilot Studio Evaluation</h1>
            <p class="subtitle">Agent Response Quality Report</p>
        </div>
        <div class="header-right">
            <div>Generated: {datetime.now().strftime("%B %d, %Y at %H:%M")}</div>
            <div>Pytest + DeepEval • M365 Agents SDK</div>
        </div>
    </header>
    
    <div class="stats-bar">
        <div class="stat total">
            <span class="stat-value">{total_tests}</span>
            <span class="stat-label">Total Tests</span>
        </div>
        <div class="stat passed">
            <span class="stat-value">{passed_tests}</span>
            <span class="stat-label">Passed</span>
        </div>
        <div class="stat failed">
            <span class="stat-value">{failed_tests}</span>
            <span class="stat-label">Failed</span>
        </div>
        <div class="stat avg">
            <span class="stat-value">{avg_score:.2f}</span>
            <span class="stat-label">Avg Score</span>
        </div>
    </div>
    
    <div class="controls">
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search by question or content...">
        </div>
        <div class="filter-btns">
            <button class="filter-btn active" data-filter="all">All</button>
            <button class="filter-btn" data-filter="passed">✓ Passed</button>
            <button class="filter-btn" data-filter="failed">✗ Failed</button>
            <button class="filter-btn" data-filter="high">High Score</button>
            <button class="filter-btn" data-filter="low">Low Score</button>
        </div>
        <button class="download-btn" onclick="downloadCSV()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Download CSV
        </button>
        <div class="metrics-legend">
            <div class="legend-item"><span class="legend-dot corr"></span>Correctness (40%)</div>
            <div class="legend-item"><span class="legend-dot rel"></span>Relevancy (25%)</div>
            <div class="legend-item"><span class="legend-dot coh"></span>Coherence (15%)</div>
            <div class="legend-item"><span class="legend-dot comp"></span>Completeness (20%)</div>
        </div>
    </div>
    
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th class="col-status">Status</th>
                    <th class="col-id">Conv ID</th>
                    <th class="col-question">Question</th>
                    <th class="col-score">Score</th>
                    <th class="col-metrics">Metrics (C / R / Co / Cm)</th>
                    <th class="col-actions">Actions</th>
                </tr>
            </thead>
            <tbody id="testTableBody">
                {table_rows_html}
            </tbody>
        </table>
        <div class="empty-state" id="emptyState" style="display: none;">
            <div class="empty-state-icon">🔍</div>
            <p>No tests match your search criteria</p>
        </div>
    </div>
    
    <!-- Details Modal -->
    <div class="modal-overlay" id="modalOverlay">
        <div class="modal">
            <div class="modal-header">
                <h2>
                    <span id="modalTitle">Test Details</span>
                    <span class="modal-status" id="modalStatus">PASSED</span>
                </h2>
                <button class="modal-close" onclick="closeModal()">×</button>
            </div>
            <div class="modal-body" id="modalBody">
                <!-- Dynamic content -->
            </div>
            <div class="modal-nav">
                <button class="nav-btn" id="prevBtn" onclick="navigateTest(-1)">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
                    Previous
                </button>
                <button class="nav-btn" id="nextBtn" onclick="navigateTest(1)">
                    Next
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
                </button>
            </div>
        </div>
    </div>
    
    <script>
        const testData = {details_json};
        let currentIndex = 0;
        
        function showDetails(index) {{
            currentIndex = index;
            const test = testData[index];
            const score = parseFloat(test.overall_score);
            const scoreClass = score >= 0.70 ? 'high' : score >= 0.50 ? 'medium' : 'low';
            
            document.getElementById('modalStatus').textContent = test.passed ? 'PASSED' : 'FAILED';
            document.getElementById('modalStatus').className = 'modal-status ' + (test.passed ? 'passed' : 'failed');
            document.getElementById('modalTitle').textContent = 'Test #' + (index + 1);
            
            document.getElementById('modalBody').innerHTML = `
                <div class="modal-meta">
                    <div class="meta-item">
                        <span class="meta-label">Conversation ID</span>
                        <span class="meta-value">${{test.conversation_id}}</span>
                    </div>
                    <div class="meta-item modal-score">
                        <span class="meta-label">Overall Score</span>
                        <span class="modal-score-value ${{scoreClass}}">${{test.overall_score}}</span>
                    </div>
                </div>
                
                <div class="content-block">
                    <h4>❓ Question</h4>
                    <p>${{escapeHtml(test.question)}}</p>
                </div>
                
                <div class="content-block">
                    <h4>✅ Expected Answer</h4>
                    <p>${{escapeHtml(test.expected)}}</p>
                </div>
                
                <div class="content-block">
                    <h4>🤖 Agent Response</h4>
                    <p>${{escapeHtml(test.actual)}}</p>
                </div>
                
                <div class="metrics-detail">
                    <div class="metric-detail-card corr">
                        <div class="metric-detail-header">
                            <span class="metric-detail-name">Correctness (40%)</span>
                            <span class="metric-detail-score">${{test.correctness_score}}</span>
                        </div>
                        <div class="metric-detail-bar">
                            <div class="metric-detail-bar-fill" style="width: ${{parseFloat(test.correctness_score) * 100}}%"></div>
                        </div>
                        <p class="metric-detail-reason">${{escapeHtml(test.correctness_reason) || 'No reason provided'}}</p>
                    </div>
                    
                    <div class="metric-detail-card rel">
                        <div class="metric-detail-header">
                            <span class="metric-detail-name">Relevancy (25%)</span>
                            <span class="metric-detail-score">${{test.relevancy_score}}</span>
                        </div>
                        <div class="metric-detail-bar">
                            <div class="metric-detail-bar-fill" style="width: ${{parseFloat(test.relevancy_score) * 100}}%"></div>
                        </div>
                        <p class="metric-detail-reason">${{escapeHtml(test.relevancy_reason) || 'No reason provided'}}</p>
                    </div>
                    
                    <div class="metric-detail-card coh">
                        <div class="metric-detail-header">
                            <span class="metric-detail-name">Coherence (15%)</span>
                            <span class="metric-detail-score">${{test.coherence_score}}</span>
                        </div>
                        <div class="metric-detail-bar">
                            <div class="metric-detail-bar-fill" style="width: ${{parseFloat(test.coherence_score) * 100}}%"></div>
                        </div>
                        <p class="metric-detail-reason">${{escapeHtml(test.coherence_reason) || 'No reason provided'}}</p>
                    </div>
                    
                    <div class="metric-detail-card comp">
                        <div class="metric-detail-header">
                            <span class="metric-detail-name">Completeness (20%)</span>
                            <span class="metric-detail-score">${{test.completeness_score}}</span>
                        </div>
                        <div class="metric-detail-bar">
                            <div class="metric-detail-bar-fill" style="width: ${{parseFloat(test.completeness_score) * 100}}%"></div>
                        </div>
                        <p class="metric-detail-reason">${{escapeHtml(test.completeness_reason) || 'No reason provided'}}</p>
                    </div>
                </div>
            `;
            
            updateNavButtons();
            document.getElementById('modalOverlay').classList.add('active');
            document.body.style.overflow = 'hidden';
        }}
        
        function closeModal() {{
            document.getElementById('modalOverlay').classList.remove('active');
            document.body.style.overflow = '';
        }}
        
        function navigateTest(direction) {{
            const visibleRows = Array.from(document.querySelectorAll('.test-row')).filter(r => r.style.display !== 'none');
            const currentVisibleIndex = visibleRows.findIndex(r => parseInt(r.dataset.index) === currentIndex);
            const newVisibleIndex = currentVisibleIndex + direction;
            
            if (newVisibleIndex >= 0 && newVisibleIndex < visibleRows.length) {{
                showDetails(parseInt(visibleRows[newVisibleIndex].dataset.index));
            }}
        }}
        
        function updateNavButtons() {{
            const visibleRows = Array.from(document.querySelectorAll('.test-row')).filter(r => r.style.display !== 'none');
            const currentVisibleIndex = visibleRows.findIndex(r => parseInt(r.dataset.index) === currentIndex);
            
            document.getElementById('prevBtn').disabled = currentVisibleIndex <= 0;
            document.getElementById('nextBtn').disabled = currentVisibleIndex >= visibleRows.length - 1;
        }}
        
        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
        // Search functionality
        document.getElementById('searchInput').addEventListener('input', function() {{
            filterTable();
        }});
        
        // Filter functionality
        document.querySelectorAll('.filter-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                filterTable();
            }});
        }});
        
        function filterTable() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const filter = document.querySelector('.filter-btn.active').dataset.filter;
            const rows = document.querySelectorAll('.test-row');
            let visibleCount = 0;
            
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                const status = row.dataset.status;
                const score = parseFloat(row.dataset.score);
                
                let matchesFilter = filter === 'all' ||
                    (filter === 'passed' && status === 'passed') ||
                    (filter === 'failed' && status === 'failed') ||
                    (filter === 'high' && score >= 0.70) ||
                    (filter === 'low' && score < 0.50);
                
                let matchesSearch = text.includes(query);
                
                if (matchesFilter && matchesSearch) {{
                    row.style.display = '';
                    visibleCount++;
                }} else {{
                    row.style.display = 'none';
                }}
            }});
            
            document.getElementById('emptyState').style.display = visibleCount === 0 ? 'block' : 'none';
        }}
        
        // Close modal on overlay click
        document.getElementById('modalOverlay').addEventListener('click', function(e) {{
            if (e.target === this) closeModal();
        }});
        
        // Close modal on Escape key
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeModal();
            if (document.getElementById('modalOverlay').classList.contains('active')) {{
                if (e.key === 'ArrowLeft') navigateTest(-1);
                if (e.key === 'ArrowRight') navigateTest(1);
            }}
        }});
        
        // Download CSV functionality
        function downloadCSV() {{
            // CSV Headers
            const headers = [
                'Test #',
                'Status',
                'Conversation ID',
                'Question',
                'Expected Answer',
                'Agent Response',
                'Overall Score',
                'Correctness Score',
                'Relevancy Score',
                'Coherence Score',
                'Completeness Score',
                'Correctness Reason',
                'Relevancy Reason',
                'Coherence Reason',
                'Completeness Reason'
            ];
            
            // Escape CSV field (handle quotes and commas)
            function escapeCSV(field) {{
                if (field === null || field === undefined) return '';
                const str = String(field);
                // If contains comma, newline, or quote, wrap in quotes and escape internal quotes
                if (str.includes(',') || str.includes('\\n') || str.includes('"') || str.includes('\\r')) {{
                    return '"' + str.replace(/"/g, '""') + '"';
                }}
                return str;
            }}
            
            // Build CSV rows from test data
            const rows = testData.map((test, index) => {{
                return [
                    index + 1,
                    test.passed ? 'PASSED' : 'FAILED',
                    test.conversation_id,
                    test.question,
                    test.expected,
                    test.actual,
                    test.overall_score,
                    test.correctness_score,
                    test.relevancy_score,
                    test.coherence_score,
                    test.completeness_score,
                    test.correctness_reason,
                    test.relevancy_reason,
                    test.coherence_reason,
                    test.completeness_reason
                ].map(escapeCSV).join(',');
            }});
            
            // Combine headers and rows
            const csvContent = [headers.join(','), ...rows].join('\\n');
            
            // Create blob and download
            const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            
            // Generate filename with timestamp
            const now = new Date();
            const timestamp = now.toISOString().slice(0, 19).replace(/[T:]/g, '-');
            const filename = `copilot-evaluation-${{timestamp}}.csv`;
            
            link.setAttribute('href', url);
            link.setAttribute('download', filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>'''
    
    # Write the HTML file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n{'='*60}")
    print(f"📊 Custom Report Generated: {output_path}")
    print(f"{'='*60}\n")

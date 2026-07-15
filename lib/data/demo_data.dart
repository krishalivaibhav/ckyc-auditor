import '../models/models.dart';

/// In-memory fallback that mirrors supabase/seed.sql. Used when Supabase isn't
/// configured (no --dart-define) so the UI is fully explorable offline and the
/// demo can never fail on a network hiccup. The shapes match schema.md exactly.
class DemoData {
  DemoData._();

  static DateTime _daysAgo(int d) =>
      DateTime.now().toUtc().subtract(Duration(days: d));

  static final List<Entity> entities = [
    const Entity(
        entityId: '11111111-1111-1111-1111-111111111111',
        type: 'company',
        name: 'Meridian Holdings Pvt Ltd',
        aliases: ['Meridian Group', 'Meridian Intl'],
        nationality: 'AE',
        dinOrCin: 'U74999MH2015PTC271234',
        source: 'internal_kyc'),
    Entity(
        entityId: '22222222-2222-2222-2222-222222222222',
        type: 'person',
        name: 'Viktor A. Kozlov',
        aliases: const ['V. Kozlov', 'Viktor Kozlow'],
        dob: DateTime.utc(1968, 3, 12),
        nationality: 'RU',
        source: 'internal_kyc'),
    const Entity(
        entityId: '33333333-3333-3333-3333-333333333333',
        type: 'company',
        name: 'Sunrise Minerals & Trading',
        aliases: ['Sunrise Mining'],
        nationality: 'ZA',
        dinOrCin: 'U13100DL2018PTC334455',
        source: 'internal_kyc'),
    Entity(
        entityId: '44444444-4444-4444-4444-444444444444',
        type: 'person',
        name: 'Amara N. Okafor',
        aliases: const ['A. Okafor'],
        dob: DateTime.utc(1981, 7, 25),
        nationality: 'NG',
        source: 'client_input'),
    const Entity(
        entityId: '55555555-5555-5555-5555-555555555555',
        type: 'company',
        name: 'BlueHarbor Financial Services',
        aliases: ['BlueHarbor FS'],
        nationality: 'SG',
        dinOrCin: 'U65999KA2016PTC556677',
        source: 'internal_kyc'),
    Entity(
        entityId: '66666666-6666-6666-6666-666666666666',
        type: 'person',
        name: 'Elena M. Rossi',
        aliases: const ['E. Rossi'],
        dob: DateTime.utc(1975, 11, 2),
        nationality: 'IT',
        source: 'internal_kyc'),
    const Entity(
        entityId: '77777777-7777-7777-7777-777777777777',
        type: 'company',
        name: 'Cedar Real Estate Ventures',
        aliases: ['Cedar REV'],
        nationality: 'LB',
        dinOrCin: 'U70100MH2019PTC778899',
        source: 'internal_kyc'),
    Entity(
        entityId: '88888888-8888-8888-8888-888888888888',
        type: 'person',
        name: 'James P. Whitfield',
        aliases: const ['J. Whitfield'],
        dob: DateTime.utc(1960, 1, 19),
        nationality: 'GB',
        source: 'client_input'),
  ];

  static final List<ResolutionVerdict> verdicts = [
    ResolutionVerdict(
        queryEntityId: '22222222-2222-2222-2222-222222222222',
        candidateId: 'ofac-8842',
        verdict: 'confirmed_match',
        confidence: 0.94,
        explanation:
            'Name matches OFAC entry "Viktor Kozlov" and nationality (RU) aligns. DOB on the SDN record (1968) matches the client DOB 1968-03-12. High-confidence true positive.',
        anchorUsed: 'none',
        resolvedAt: _daysAgo(2)),
    ResolutionVerdict(
        queryEntityId: '44444444-4444-4444-4444-444444444444',
        candidateId: 'pep-5567',
        verdict: 'needs_review',
        confidence: 0.55,
        explanation:
            'Name similarity to a PEP list entry is moderate (0.66) but no DOB or nationality on the PEP record to corroborate. Insufficient anchors to confirm — route to human review.',
        anchorUsed: 'none',
        resolvedAt: _daysAgo(1)),
    ResolutionVerdict(
        queryEntityId: '11111111-1111-1111-1111-111111111111',
        candidateId: 'ofac-2201',
        verdict: 'false_positive',
        confidence: 0.28,
        explanation:
            'Candidate "Meridian Trading LLC" shares only a partial name token. CIN anchor U74999MH2015PTC271234 verified against MCA — distinct legal entity in a different jurisdiction. Cleared.',
        anchorUsed: 'CIN',
        resolvedAt: _daysAgo(3)),
    ResolutionVerdict(
        queryEntityId: '33333333-3333-3333-3333-333333333333',
        candidateId: 'none',
        verdict: 'needs_review',
        confidence: 0.50,
        explanation:
            'No direct sanctions candidate, but sector (Mining) and jurisdiction exposure are elevated. Flagged on adverse-media signal rather than list match.',
        anchorUsed: 'none',
        resolvedAt: _daysAgo(3)),
  ];

  static final List<RiskEvent> riskEvents = [
    RiskEvent(
        eventId: 're1',
        entityId: '22222222-2222-2222-2222-222222222222',
        eventType: 'sanctions_hit',
        severity: 'high',
        detectedAt: _daysAgo(2),
        sourceRefs: const ['ofac-8842']),
    RiskEvent(
        eventId: 're2',
        entityId: '22222222-2222-2222-2222-222222222222',
        eventType: 'adverse_media',
        severity: 'high',
        detectedAt: _daysAgo(1),
        sourceRefs: const ['https://news.example.com/kozlov-probe']),
    RiskEvent(
        eventId: 're3',
        entityId: '33333333-3333-3333-3333-333333333333',
        eventType: 'adverse_media',
        severity: 'medium',
        detectedAt: _daysAgo(5),
        sourceRefs: const ['https://news.example.com/sunrise-minerals-inquiry']),
    RiskEvent(
        eventId: 're4',
        entityId: '33333333-3333-3333-3333-333333333333',
        eventType: 'ownership_change',
        severity: 'medium',
        detectedAt: _daysAgo(3),
        sourceRefs: const ['https://registry.example.com/sunrise-ubo']),
    RiskEvent(
        eventId: 're5',
        entityId: '44444444-4444-4444-4444-444444444444',
        eventType: 'adverse_media',
        severity: 'low',
        detectedAt: _daysAgo(8),
        sourceRefs: const ['https://news.example.com/okafor-mention']),
    RiskEvent(
        eventId: 're6',
        entityId: '77777777-7777-7777-7777-777777777777',
        eventType: 'adverse_media',
        severity: 'medium',
        detectedAt: _daysAgo(6),
        sourceRefs: const ['https://news.example.com/cedar-aml-fine']),
  ];

  // report_timeline entries live on their DraftReport below (schema.md §7:
  // report_timeline.report_id, not entity_id). Cedar Real Estate (777...) has
  // a risk_event but no filed report yet, so it has no detailed timeline —
  // that's the expected shape, not a gap.
  static final List<DraftReport> reports = [
    DraftReport(
      reportId: 'aaaaaaaa-0000-0000-0000-000000000001',
      entityId: '22222222-2222-2222-2222-222222222222',
      status: 'draft',
      summary:
          'Viktor A. Kozlov is a confirmed match against the OFAC SDN list (Ukraine-related program), corroborated by matching nationality and date of birth. Adverse media within the last 24 hours reports an active corruption investigation involving cross-border transfers. Combined sanctions and media exposure warrant filing a Suspicious Activity Report.',
      citations: const [
        Citation(
            claim: 'Confirmed match against the OFAC SDN list',
            sourceUrl: 'https://www.treasury.gov/ofac/downloads/sdn.csv',
            excerpt: 'Designated under Ukraine-related sanctions program.'),
        Citation(
            claim:
                'Active corruption investigation involving cross-border transfers',
            sourceUrl: 'https://news.example.com/kozlov-probe',
            excerpt:
                'Reportedly under investigation for cross-border laundering.'),
      ],
      timeline: [
        TimelineEntry(
            id: 'tl1',
            reportId: 'aaaaaaaa-0000-0000-0000-000000000001',
            eventDate: _daysAgo(2),
            event: 'Added to OFAC SDN list',
            sourceUrl: 'https://www.treasury.gov/ofac/downloads/sdn.csv',
            excerpt: 'Designated under Ukraine-related sanctions program.'),
        TimelineEntry(
            id: 'tl2',
            reportId: 'aaaaaaaa-0000-0000-0000-000000000001',
            eventDate: _daysAgo(1),
            event: 'Named in international corruption probe',
            sourceUrl: 'https://news.example.com/kozlov-probe',
            excerpt:
                'Reportedly under investigation for cross-border laundering.'),
      ],
    ),
    DraftReport(
      reportId: 'aaaaaaaa-0000-0000-0000-000000000002',
      entityId: '33333333-3333-3333-3333-333333333333',
      status: 'draft',
      summary:
          'Sunrise Minerals & Trading shows no direct sanctions match but presents elevated risk: a regulatory inquiry into export fund sources and a recent change of ultimate beneficial owner to a high-risk jurisdiction. Recommend enhanced due diligence and human review before any transaction approval.',
      citations: const [
        Citation(
            claim: 'Regulatory inquiry into export fund sources',
            sourceUrl: 'https://news.example.com/sunrise-minerals-inquiry',
            excerpt: 'Local regulator queries source of mineral export funds.'),
        Citation(
            claim:
                'Change of ultimate beneficial owner to a high-risk jurisdiction',
            sourceUrl: 'https://registry.example.com/sunrise-ubo',
            excerpt: 'New UBO registered in a high-risk jurisdiction.'),
      ],
      timeline: [
        TimelineEntry(
            id: 'tl3',
            reportId: 'aaaaaaaa-0000-0000-0000-000000000002',
            eventDate: _daysAgo(5),
            event: 'Regulatory inquiry opened',
            sourceUrl: 'https://news.example.com/sunrise-minerals-inquiry',
            excerpt: 'Local regulator queries source of mineral export funds.'),
        TimelineEntry(
            id: 'tl4',
            reportId: 'aaaaaaaa-0000-0000-0000-000000000002',
            eventDate: _daysAgo(3),
            event: 'Ultimate beneficial owner changed',
            sourceUrl: 'https://registry.example.com/sunrise-ubo',
            excerpt: 'New UBO registered in a high-risk jurisdiction.'),
      ],
    ),
  ];

  static final List<AuditEntry> audit = [
    AuditEntry(
        logId: 'al1',
        actor: 'agent:sanctions-agent',
        action: 'screened_entity',
        entityId: '22222222-2222-2222-2222-222222222222',
        timestamp: _daysAgo(2),
        details: const {'candidates': 2}),
    AuditEntry(
        logId: 'al2',
        actor: 'agent:entity-resolution',
        action: 'resolved_verdict',
        entityId: '22222222-2222-2222-2222-222222222222',
        timestamp: _daysAgo(2),
        details: const {'verdict': 'confirmed_match'}),
    AuditEntry(
        logId: 'al3',
        actor: 'agent:media-orchestrator',
        action: 'flagged_risk_event',
        entityId: '22222222-2222-2222-2222-222222222222',
        timestamp: _daysAgo(1),
        details: const {'severity': 'high'}),
    AuditEntry(
        logId: 'al4',
        actor: 'agent:investigation-agent',
        action: 'drafted_report',
        entityId: '22222222-2222-2222-2222-222222222222',
        timestamp: _daysAgo(1),
        details: const {'report_id': 'aaaaaaaa-0000-0000-0000-000000000001'}),
  ];

  // ═══════════════════════════════════════════════════════════════════════════
  // New architecture (05_SAMAKSH_ui.md) — six-screen demo fixtures.
  // Served offline by DemoRepository; SupabaseRepository stubs these until a
  // migration lands. Keyed by the same client ids across all maps below.
  // ═══════════════════════════════════════════════════════════════════════════

  static const _cr = 10000000.0; // 1 crore in ₹
  static const _lakh = 100000.0; // 1 lakh in ₹

  /// Screen 1 — alert queue. Note c-2002 (HIGH on ₹50cr) is meant to outrank
  /// c-2001 (CRITICAL on ₹2L) once the UI sorts by tier × exposure.
  static final List<Alert> alerts = [
    Alert(
        clientId: 'c-2002',
        name: 'Vertex Commodities Pvt Ltd',
        type: 'Company',
        tier: RiskTier.high,
        status: 'open',
        exposureInr: 50 * _cr,
        caseId: 'case-2002'),
    Alert(
        clientId: 'c-2001',
        name: 'Rajesh Malhotra',
        type: 'Individual',
        tier: RiskTier.critical,
        status: 'in_review',
        exposureInr: 2 * _lakh,
        caseId: 'case-2001'),
    Alert(
        clientId: 'c-2003',
        name: 'Sterling Exports Ltd',
        type: 'Company',
        tier: RiskTier.edd, // de-escalated from HIGH — see timeline
        status: 'open',
        exposureInr: 8 * _cr,
        caseId: 'case-2003'),
    Alert(
        clientId: 'c-3001',
        name: 'Neha Kapoor',
        type: 'Individual',
        tier: RiskTier.eddLite,
        status: 'open',
        exposureInr: 40 * _lakh),
    Alert(
        clientId: 'c-3002',
        name: 'Coastal Logistics LLP',
        type: 'Company',
        tier: RiskTier.monitor,
        status: 'open',
        exposureInr: 12 * _lakh),
  ];

  /// Screen 5 — the suppression log. The three canonical rejects from the spec.
  static const List<Suppression> suppressions = [
    Suppression(
        customer: 'Anand Sharma',
        matched: 'NSE/SEBI debarred',
        method: 'PAN_MISMATCH_REJECT',
        reason:
            'PAN BGJPS5517E ≠ ATFPS5670Q → different person. Names collide but the identifiers do not.'),
    Suppression(
        customer: 'Amir Khan',
        matched: 'MHA UAPA',
        method: 'ALIAS_BARE_REJECT',
        reason:
            'Matched only the bare alias "Amir Khan" with no DOB, PAN or nationality to corroborate — requires a second identifier before we will raise it.'),
    Suppression(
        customer: 'Ajay Kumar',
        matched: 'PEP + debarred',
        method: 'CROSS_LIST_NO_LINK',
        reason:
            'The two source lists share zero identifiers, so we never auto-link them into a single higher-risk entity.'),
  ];

  /// Screen 2 — Entity 360 (customer ←→ matched watchlist entry), keyed by
  /// client id. Includes both suppressed matches (rejectionReason set) and a
  /// confirmed high-risk case.
  static final Map<String, Entity360> entity360 = {
    'c-1001': Entity360(
      customer: const Customer(
          clientId: 'c-1001',
          name: 'Anand Sharma',
          type: 'Individual',
          pan: 'BGJPS5517E',
          city: 'Mumbai'),
      assessment: const RiskAssessment(
          tier: RiskTier.monitor,
          score: 0.12,
          exposureInr: 5 * _lakh,
          gatesFired: [],
          suppressions: ['PAN_MISMATCH_REJECT']),
      candidate: const Candidate(
          candidateId: 'nse-debar-4471',
          matchedName: 'Anand Sharma',
          matchedPan: 'ATFPS5670Q',
          matchedType: 'Individual',
          listName: 'NSE/SEBI debarred',
          matchMethod: 'NAME_ONLY',
          confidence: 0.41,
          rejectionReason:
              'PAN mismatch: client BGJPS5517E vs debarred entry ATFPS5670Q. Same name, different person — not raised.'),
    ),
    'c-2001': Entity360(
      customer: const Customer(
          clientId: 'c-2001',
          name: 'Rajesh Malhotra',
          type: 'Individual',
          pan: 'AAAPM1234C',
          city: 'Delhi'),
      assessment: const RiskAssessment(
          tier: RiskTier.critical,
          score: 0.97,
          exposureInr: 2 * _lakh,
          gatesFired: ['UAPA_EXACT_PAN', 'ADVERSE_MEDIA_CORROBORATION'],
          suppressions: []),
      candidate: const Candidate(
          candidateId: 'mha-uapa-0091',
          matchedName: 'Rajesh Malhotra',
          matchedPan: 'AAAPM1234C',
          matchedType: 'Individual',
          listName: 'MHA UAPA',
          matchMethod: 'PAN_EXACT',
          confidence: 0.98),
    ),
    'c-2002': Entity360(
      customer: const Customer(
          clientId: 'c-2002',
          name: 'Vertex Commodities Pvt Ltd',
          type: 'Company',
          pan: 'AABCV7788K',
          city: 'Ahmedabad'),
      assessment: const RiskAssessment(
          tier: RiskTier.high,
          score: 0.74,
          exposureInr: 50 * _cr,
          gatesFired: ['SEBI_DEBAR_CIN_MATCH', 'HIGH_EXPOSURE'],
          suppressions: []),
      candidate: const Candidate(
          candidateId: 'sebi-debar-2210',
          matchedName: 'Vertex Commodities Private Limited',
          matchedPan: 'AABCV7788K',
          matchedType: 'Company',
          listName: 'NSE/SEBI debarred',
          matchMethod: 'CIN_EXACT',
          confidence: 0.91),
    ),
  };

  /// Screen 3 — risk timeline, keyed by client id. c-2003 carries the
  /// de-escalation (SEBI order revoked → tier goes DOWN).
  static final Map<String, List<TimelineEvent>> timelines = {
    'c-2001': [
      TimelineEvent(
          id: 'te-2001-1',
          clientId: 'c-2001',
          date: _daysAgo(20),
          event: 'Onboarded — routine screening, no hits',
          evidenceRefs: const [],
          tierBefore: RiskTier.monitor,
          tierAfter: RiskTier.monitor),
      TimelineEvent(
          id: 'te-2001-2',
          clientId: 'c-2001',
          date: _daysAgo(4),
          event:
              'Exact PAN match to MHA UAPA notification — escalated to CRITICAL',
          evidenceRefs: const ['EV-001'],
          tierBefore: RiskTier.monitor,
          tierAfter: RiskTier.critical),
      TimelineEvent(
          id: 'te-2001-3',
          clientId: 'c-2001',
          date: _daysAgo(3),
          event: 'Adverse media corroborates listing',
          evidenceRefs: const ['EV-002'],
          tierBefore: RiskTier.critical,
          tierAfter: RiskTier.critical),
    ],
    'c-2003': [
      TimelineEvent(
          id: 'te-2003-1',
          clientId: 'c-2003',
          date: _daysAgo(60),
          event: 'Named in SEBI interim debarment order — escalated to HIGH',
          evidenceRefs: const ['EV-101'],
          tierBefore: RiskTier.monitor,
          tierAfter: RiskTier.high),
      TimelineEvent(
          id: 'te-2003-2',
          clientId: 'c-2003',
          date: _daysAgo(7),
          event:
              'SEBI interim order revoked on appeal — risk DE-ESCALATED to EDD',
          evidenceRefs: const ['EV-102'],
          tierBefore: RiskTier.high,
          tierAfter: RiskTier.edd),
    ],
  };

  /// Screen 4 + 6 — cases (three-column evidence + SAR), keyed by case id.
  static final Map<String, Case> cases = {
    'case-2001': Case(
      caseId: 'case-2001',
      clientId: 'c-2001',
      customer: const Customer(
          clientId: 'c-2001',
          name: 'Rajesh Malhotra',
          type: 'Individual',
          pan: 'AAAPM1234C',
          city: 'Delhi'),
      assessment: const RiskAssessment(
          tier: RiskTier.critical,
          score: 0.97,
          exposureInr: 2 * _lakh,
          gatesFired: ['UAPA_EXACT_PAN', 'ADVERSE_MEDIA_CORROBORATION']),
      evidence: const [
        Evidence(
            evId: 'EV-001',
            column: EvidenceColumn.confirmed,
            claim: 'PAN exact match to MHA UAPA notification',
            sourceName: 'MHA UAPA notification S.O. 4231(E)',
            sourceUrl:
                'https://www.mha.gov.in/sites/default/files/uapa-notification.pdf',
            excerpt:
                'Individual listed under the Unlawful Activities (Prevention) Act; PAN AAAPM1234C.',
            confidence: 0.98),
        Evidence(
            evId: 'EV-002',
            column: EvidenceColumn.confirmed,
            claim: 'Adverse media naming the individual in a terror-financing probe',
            sourceName: 'The Hindu',
            sourceUrl: 'https://www.thehindu.com/news/example-uapa-probe',
            excerpt:
                'Investigators named Rajesh Malhotra among those under scrutiny for cross-border transfers.',
            confidence: 0.71),
        Evidence(
            evId: 'EV-003',
            column: EvidenceColumn.correlated,
            claim: 'Same name and city as a separate PEP record — no shared identifier',
            sourceName: 'PEP register',
            excerpt:
                'A "Rajesh Malhotra" of Delhi appears on a PEP list, but with no matching PAN or DOB.',
            confidence: 0.35),
        Evidence(
            evId: 'EV-004',
            column: EvidenceColumn.missing,
            claim: 'Company registry record for the linked entity not retrievable',
            sourceName: 'MCA21',
            excerpt: 'Lookup returned no record; registry may be stale.'),
      ],
      sar: const Sar(
        caseId: 'case-2001',
        body:
            'Subject Rajesh Malhotra (PAN AAAPM1234C) is an exact PAN match to an individual '
            'listed under the Unlawful Activities (Prevention) Act [EV-001]. Adverse media '
            'independently names the subject in a terror-financing investigation involving '
            'cross-border transfers [EV-002]. Given a confirmed UAPA listing corroborated by '
            'media, we recommend filing a Suspicious Activity Report and freezing further '
            'transactions pending review.',
        citationCoverage: 0.86,
        unverifiedClaims: [
          'Alleged offshore account in Dubai — no corroborating source located.',
          'Reported family link to a second listed individual — could not be verified.',
        ],
        status: 'draft',
      ),
      reviewerActions: const [],
    ),
    'case-2002': Case(
      caseId: 'case-2002',
      clientId: 'c-2002',
      customer: const Customer(
          clientId: 'c-2002',
          name: 'Vertex Commodities Pvt Ltd',
          type: 'Company',
          pan: 'AABCV7788K',
          city: 'Ahmedabad'),
      assessment: const RiskAssessment(
          tier: RiskTier.high,
          score: 0.74,
          exposureInr: 50 * _cr,
          gatesFired: ['SEBI_DEBAR_CIN_MATCH', 'HIGH_EXPOSURE']),
      evidence: const [
        Evidence(
            evId: 'EV-050',
            column: EvidenceColumn.confirmed,
            claim: 'CIN exact match to an NSE/SEBI debarment order',
            sourceName: 'SEBI order WTM/2023/1187',
            sourceUrl: 'https://www.sebi.gov.in/enforcement/orders/example.pdf',
            excerpt: 'Entity debarred from the securities market for two years.',
            confidence: 0.91),
        Evidence(
            evId: 'EV-051',
            column: EvidenceColumn.correlated,
            claim: 'Directors overlap with a second debarred company',
            sourceName: 'MCA21 director index',
            excerpt: 'Two common DINs across the two entities.',
            confidence: 0.48),
        Evidence(
            evId: 'EV-052',
            column: EvidenceColumn.missing,
            claim: 'Ultimate beneficial owner declaration not on file',
            sourceName: 'Internal KYC',
            excerpt: 'UBO field blank in the onboarding packet.'),
      ],
      sar: const Sar(
        caseId: 'case-2002',
        body:
            'Vertex Commodities Pvt Ltd (CIN-matched) is subject to an active SEBI debarment '
            'order [EV-050]. With ₹50cr of exposure and a directorship overlap with a second '
            'debarred entity [EV-051], enhanced due diligence and senior sign-off are '
            'recommended before any further limit is extended.',
        citationCoverage: 0.79,
        unverifiedClaims: [
          'Suspected shell subsidiary in Singapore — registry lookup pending.',
        ],
        status: 'draft',
      ),
    ),
    'case-2003': Case(
      caseId: 'case-2003',
      clientId: 'c-2003',
      customer: const Customer(
          clientId: 'c-2003',
          name: 'Sterling Exports Ltd',
          type: 'Company',
          pan: 'AACCS9012F',
          city: 'Surat'),
      assessment: const RiskAssessment(
          tier: RiskTier.edd,
          score: 0.44,
          exposureInr: 8 * _cr,
          gatesFired: ['SEBI_ORDER_REVOKED']),
      evidence: const [
        Evidence(
            evId: 'EV-101',
            column: EvidenceColumn.confirmed,
            claim: 'Named in a SEBI interim debarment order',
            sourceName: 'SEBI interim order',
            sourceUrl: 'https://www.sebi.gov.in/enforcement/orders/interim.pdf',
            excerpt: 'Interim restraint pending investigation.',
            confidence: 0.88),
        Evidence(
            evId: 'EV-102',
            column: EvidenceColumn.confirmed,
            claim: 'SEBI interim order revoked on appeal',
            sourceName: 'SAT order',
            sourceUrl: 'https://sat.gov.in/orders/example-revocation.pdf',
            excerpt:
                'Securities Appellate Tribunal set aside the interim restraint.',
            confidence: 0.9),
      ],
      sar: null,
    ),
  };

  /// Before/after toggle. Baseline is the naive screen; ours is this system.
  static const Metrics metrics = Metrics(
    baseline:
        MetricsSnapshot(label: 'BASELINE', alerts: 474, precision: 0.169, recall: 0.94),
    ours: MetricsSnapshot(label: 'OURS', alerts: 80, precision: 0.71, recall: 0.90),
  );
}

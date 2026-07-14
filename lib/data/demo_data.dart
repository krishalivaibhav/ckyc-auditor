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
        candidateId: null,
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

  static final List<Evidence> evidence = [
    Evidence(
        id: 'ev1',
        entityId: '22222222-2222-2222-2222-222222222222',
        eventDate: _daysAgo(2),
        event: 'Added to OFAC SDN list',
        sourceUrl: 'https://www.treasury.gov/ofac/downloads/sdn.csv',
        excerpt: 'Designated under Ukraine-related sanctions program.'),
    Evidence(
        id: 'ev2',
        entityId: '22222222-2222-2222-2222-222222222222',
        eventDate: _daysAgo(1),
        event: 'Named in international corruption probe',
        sourceUrl: 'https://news.example.com/kozlov-probe',
        excerpt: 'Reportedly under investigation for cross-border laundering.'),
    Evidence(
        id: 'ev3',
        entityId: '33333333-3333-3333-3333-333333333333',
        eventDate: _daysAgo(5),
        event: 'Regulatory inquiry opened',
        sourceUrl: 'https://news.example.com/sunrise-minerals-inquiry',
        excerpt: 'Local regulator queries source of mineral export funds.'),
    Evidence(
        id: 'ev4',
        entityId: '33333333-3333-3333-3333-333333333333',
        eventDate: _daysAgo(3),
        event: 'Ultimate beneficial owner changed',
        sourceUrl: 'https://registry.example.com/sunrise-ubo',
        excerpt: 'New UBO registered in a high-risk jurisdiction.'),
    Evidence(
        id: 'ev5',
        entityId: '77777777-7777-7777-7777-777777777777',
        eventDate: _daysAgo(6),
        event: 'AML penalty reported',
        sourceUrl: 'https://news.example.com/cedar-aml-fine',
        excerpt: 'Fined for weak transaction-monitoring controls.'),
  ];

  static final List<DraftReport> reports = [
    const DraftReport(
      reportId: 'aaaaaaaa-0000-0000-0000-000000000001',
      entityId: '22222222-2222-2222-2222-222222222222',
      status: 'pending',
      summary:
          'Viktor A. Kozlov is a confirmed match against the OFAC SDN list (Ukraine-related program), corroborated by matching nationality and date of birth. Adverse media within the last 24 hours reports an active corruption investigation involving cross-border transfers. Combined sanctions and media exposure warrant filing a Suspicious Activity Report.',
      citations: [
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
    ),
    const DraftReport(
      reportId: 'aaaaaaaa-0000-0000-0000-000000000002',
      entityId: '33333333-3333-3333-3333-333333333333',
      status: 'pending',
      summary:
          'Sunrise Minerals & Trading shows no direct sanctions match but presents elevated risk: a regulatory inquiry into export fund sources and a recent change of ultimate beneficial owner to a high-risk jurisdiction. Recommend enhanced due diligence and human review before any transaction approval.',
      citations: [
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
}

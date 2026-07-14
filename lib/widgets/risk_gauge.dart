import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Radial confidence gauge — a single hero number (the verdict confidence)
/// with a supporting arc. One measure, one color; the number is the headline
/// and the arc gives it magnitude (dataviz: a headline metric wants a hero
/// number, not a busy chart).
class RiskGauge extends StatelessWidget {
  final double value; // 0..1
  final Color color;
  final String caption;

  const RiskGauge({
    super.key,
    required this.value,
    required this.color,
    required this.caption,
  });

  @override
  Widget build(BuildContext context) {
    final v = value.clamp(0.0, 1.0);
    final muted = Theme.of(context).colorScheme.onSurfaceVariant;
    return SizedBox(
      width: 148,
      height: 120,
      child: CustomPaint(
        painter: _GaugePainter(
          value: v,
          color: color,
          track: Theme.of(context).colorScheme.outlineVariant,
        ),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(height: 22),
              Text(
                '${(v * 100).round()}',
                style: TextStyle(
                  fontSize: 34,
                  fontWeight: FontWeight.w700,
                  color: color,
                  height: 1,
                ),
              ),
              Text('confidence',
                  style: TextStyle(fontSize: 11, color: muted)),
              const SizedBox(height: 2),
              Text(caption,
                  style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: color)),
            ],
          ),
        ),
      ),
    );
  }
}

class _GaugePainter extends CustomPainter {
  final double value;
  final Color color;
  final Color track;
  _GaugePainter(
      {required this.value, required this.color, required this.track});

  // 240° sweep starting at 150° (bottom-left) so the arc opens downward.
  static const double _start = math.pi * 0.833;
  static const double _sweep = math.pi * 1.333;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromLTWH(12, 12, size.width - 24, size.width - 24);
    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.round
      ..color = track;
    canvas.drawArc(rect, _start, _sweep, false, base);

    final fg = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 10
      ..strokeCap = StrokeCap.round
      ..color = color;
    canvas.drawArc(rect, _start, _sweep * value, false, fg);
  }

  @override
  bool shouldRepaint(_GaugePainter old) =>
      old.value != value || old.color != color || old.track != track;
}

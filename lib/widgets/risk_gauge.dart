import 'dart:math' as math;
import 'package:flutter/material.dart';

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
      // Expanded to a perfect square, creating a uniform canvas for the painter.
      // This stops the text from squishing into the arc limits.
      width: 190,
      height: 190,
      child: TweenAnimationBuilder<double>(
        tween: Tween<double>(begin: 0.0, end: v),
        duration: const Duration(milliseconds: 1400),
        curve: Curves.easeOutCubic,
        builder: (context, animValue, child) {
          return CustomPaint(
            painter: _GaugePainter(
              value: animValue,
              color: color,
              track: Theme.of(context).colorScheme.outlineVariant.withValues(alpha: 0.3),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center, // Naturally centers in the expanded box
              children: [
                const SizedBox(height: 16), // Slight offset to push text down into the open bottom of the arc
                Text(
                  '${(animValue * 100).round()}',
                  style: TextStyle(
                    fontSize: 48, // Much larger and legible
                    fontWeight: FontWeight.w800,
                    color: color,
                    height: 1,
                  ),
                ),
                const SizedBox(height: 4),
                Text('confidence',
                    style: TextStyle(fontSize: 12, color: muted, letterSpacing: 0.8)),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(caption,
                      style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: color)),
                ),
              ],
            ),
          );
        },
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

  static const double _start = math.pi * 0.833;
  static const double _sweep = math.pi * 1.333;

  @override
  void paint(Canvas canvas, Size size) {
    // Dynamically calculate the drawing rect to accommodate the stroke width
    // ensuring the arc doesn't clip the edges of the box
    const strokeWidth = 14.0;
    final rect = Rect.fromLTWH(
      strokeWidth / 2,
      strokeWidth / 2,
      size.width - strokeWidth,
      size.height - strokeWidth,
    );

    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..color = track;
    canvas.drawArc(rect, _start, _sweep, false, base);

    final fg = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..color = color;
    canvas.drawArc(rect, _start, _sweep * value, false, fg);
  }

  @override
  bool shouldRepaint(_GaugePainter old) =>
      old.value != value || old.color != color || old.track != track;
}
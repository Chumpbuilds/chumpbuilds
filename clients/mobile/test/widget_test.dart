import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:x87_mobile/main.dart';

void main() {
  testWidgets('X87App bootstrap screen shows branding immediately',
      (WidgetTester tester) async {
    // Pump without settling — the bootstrap screen renders synchronously
    // before any async init starts, so branding is visible right away.
    await tester.pumpWidget(const X87App());

    expect(find.text('Welcome to X87 Player'), findsOneWidget);
    expect(find.byIcon(Icons.tv), findsOneWidget);
  });

  testWidgets('X87App applies dark theme with correct background colour',
      (WidgetTester tester) async {
    await tester.pumpWidget(const X87App());

    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.theme?.brightness, Brightness.dark);
    expect(app.theme?.scaffoldBackgroundColor, const Color(0xFF1E1E1E));
  });

  testWidgets('X87App accepts a custom home widget override',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      X87App(home: const Center(child: Text('Custom Home'))),
    );

    expect(find.text('Custom Home'), findsOneWidget);
  });
}

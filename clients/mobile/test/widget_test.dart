import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:x87_mobile/main.dart';

void main() {
  testWidgets('X87 home screen shows title', (WidgetTester tester) async {
    await tester.pumpWidget(const X87App());

    expect(find.text('X87 Player'), findsOneWidget);
    expect(find.text('X87 IPTV Player'), findsOneWidget);
  });
}

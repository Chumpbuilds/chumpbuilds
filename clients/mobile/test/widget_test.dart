import 'package:flutter_test/flutter_test.dart';

import 'package:x87_mobile/main.dart';

void main() {
  testWidgets('X87App shows HomeScreen when license is valid',
      (WidgetTester tester) async {
    // Provide startWithHome: true to skip the license screen and render the
    // home screen directly — no network calls, no SharedPreferences needed.
    await tester.pumpWidget(const X87App(startWithHome: true));

    expect(find.text('X87 Player'), findsOneWidget);
    expect(find.text('Welcome to X87 Player'), findsOneWidget);
    expect(find.text('License: Active ✅'), findsOneWidget);
  });

  testWidgets('X87App shows LicenseScreen when license is not valid',
      (WidgetTester tester) async {
    await tester.pumpWidget(const X87App(startWithHome: false));

    expect(find.text('🔑 License Activation'), findsOneWidget);
    expect(find.text('Activate License'), findsOneWidget);
    expect(find.text('Exit Application'), findsOneWidget);
  });
}


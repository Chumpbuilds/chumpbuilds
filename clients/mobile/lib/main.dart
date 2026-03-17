import 'package:flutter/material.dart';

void main() {
  runApp(const X87App());
}

class X87App extends StatelessWidget {
  const X87App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'X87 Player',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1E88E5),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        brightness: Brightness.dark,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('X87 Player'),
        centerTitle: true,
      ),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.play_circle_outline,
              size: 96,
              color: Color(0xFF1E88E5),
            ),
            SizedBox(height: 24),
            Text(
              'X87 IPTV Player',
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),
            SizedBox(height: 12),
            Text(
              'Coming Soon',
              style: TextStyle(
                fontSize: 18,
                color: Colors.grey,
              ),
            ),
            // TODO: Replace this screen with the license activation screen
            // and IPTV login screen once the backend integration is complete.
          ],
        ),
      ),
    );
  }
}

// LiveTVScreen.dart

import 'package:flutter/material.dart';

class LiveTVScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Live TV'),
      ),
      body: Center(
        child: Text('Watch Live TV here!'),
      ),
    );
  }
}
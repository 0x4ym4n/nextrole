import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nextrole/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });
  http.Response metadata() => http.Response(
    jsonEncode({
      'countries': ['AE'],
      'sources': ['Fixture'],
      'dataset': 'synthetic-functional-fixtures',
    }),
    200,
  );
  testWidgets('search contract, ranking evidence and saving', (tester) async {
    Map<String, dynamic>? submitted;
    final client = MockClient((r) async {
      if (r.method == 'GET') {
        return metadata();
      }
      submitted = jsonDecode(r.body);
      return http.Response(
        jsonEncode({
          'results': [
            {
              'id': 'a',
              'title': 'Flutter Developer',
              'company': 'Example',
              'location': 'Dubai',
              'source': 'Fixture',
              'url': '',
              'description': 'Flutter and Dart',
              'work_mode': 'remote',
              'score': 1.0,
              'match_type': 'exact',
              'explanation': 'Title phrase matches.',
              'matched_skills': ['Flutter'],
              'missing_skills': ['Dart'],
            },
          ],
          'page': 1,
          'total_count': 1,
          'has_more': false,
        }),
        200,
      );
    });
    await tester.pumpWidget(NextRoleApp(client: client));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'Flutter Developer');
    await tester.tap(find.text('Find my next role ↗'));
    await tester.pumpAndSettle();
    expect(submitted?['query'], 'Flutter Developer');
    expect(submitted?['mode'], 'hybrid');
    await tester.scrollUntilVisible(
      find.text('Exact title match'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('Exact title match'), findsOneWidget);
    await tester.tap(find.byTooltip('Save Flutter Developer'));
    await tester.pumpAndSettle();
    expect(find.text('Saved (1)'), findsOneWidget);
  });
  testWidgets('empty search does not call API', (tester) async {
    int posts = 0;
    final client = MockClient((r) async {
      if (r.method == 'POST') {
        posts++;
      }
      return metadata();
    });
    await tester.pumpWidget(NextRoleApp(client: client));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Find my next role ↗'));
    await tester.pumpAndSettle();
    expect(posts, 0);
    expect(find.text('Enter a role or skill.'), findsOneWidget);
  });
  testWidgets('unavailable model is an error', (tester) async {
    final client = MockClient(
      (r) async => r.method == 'GET'
          ? metadata()
          : http.Response('{"error":"semantic model unavailable"}', 503),
    );
    await tester.pumpWidget(NextRoleApp(client: client));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'Developer');
    await tester.tap(find.text('Find my next role ↗'));
    await tester.pumpAndSettle();
    expect(find.text('semantic model unavailable'), findsOneWidget);
  });
  testWidgets('Arabic layout direction', (tester) async {
    await tester.pumpWidget(
      NextRoleApp(client: MockClient((r) async => metadata())),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('العربية'));
    await tester.pumpAndSettle();
    expect(find.text('المسمى أو المهارات'), findsOneWidget);
    expect(
      Directionality.of(tester.element(find.text('المسمى أو المهارات'))),
      TextDirection.rtl,
    );
  });
}

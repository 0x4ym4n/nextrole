import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

void main() => runApp(const NextRoleApp());
const apiBase = String.fromEnvironment(
  'NEXTROLE_API',
  defaultValue: 'http://10.0.2.2:8090',
);
const ink = Color(0xff173c37);
const green = Color(0xff205d4e);

class NextRoleApp extends StatelessWidget {
  const NextRoleApp({super.key, this.client});
  final http.Client? client;
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'NextRole',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: green),
      scaffoldBackgroundColor: const Color(0xfff7f8f3),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(color: ink, fontWeight: FontWeight.w600),
      ),
    ),
    home: SearchPage(client: client ?? http.Client()),
  );
}

class SearchPage extends StatefulWidget {
  const SearchPage({super.key, required this.client});
  final http.Client client;
  @override
  State<SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  final query = TextEditingController(), profile = TextEditingController();
  String work = '', mode = 'hybrid', country = '', jobType = '', source = '';
  String? error;
  bool busy = false,
      hasMore = false,
      showSaved = false,
      arabic = false,
      searched = false;
  int page = 1, total = 0;
  List<Map<String, dynamic>> jobs = [], saved = [];
  List<String> countries = [], sources = [];
  String dataset = 'Connecting to the local API…';
  Map<String, dynamic>? submitted;
  String t(String en, String ar) => arabic ? ar : en;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = jsonDecode(prefs.getString('nextrole_saved') ?? '[]');
      if (mounted && stored is List) {
        setState(
          () =>
              saved = stored.map((e) => Map<String, dynamic>.from(e)).toList(),
        );
      }
      final r = await widget.client
          .get(Uri.parse('$apiBase/api/v1/metadata'))
          .timeout(const Duration(seconds: 10));
      if (r.statusCode != 200) {
        throw Exception('API unavailable');
      }
      final m = jsonDecode(r.body) as Map<String, dynamic>;
      if (!mounted) {
        return;
      }
      setState(() {
        countries = List<String>.from(m['countries']);
        sources = List<String>.from(m['sources']);
        dataset = m['dataset'];
      });
    } catch (_) {
      if (mounted) {
        setState(
          () =>
              error = 'Could not connect. Check that the local API is running.',
        );
      }
    }
  }

  @override
  void dispose() {
    query.dispose();
    profile.dispose();
    widget.client.close();
    super.dispose();
  }

  Future<void> search({bool more = false}) async {
    FocusManager.instance.primaryFocus?.unfocus();
    if (busy) {
      return;
    }
    if (query.text.trim().isEmpty && !more) {
      setState(
        () => error = t('Enter a role or skill.', 'أدخل المسمى أو المهارة.'),
      );
      return;
    }
    final request = more && submitted != null
        ? {...submitted!, 'page': page + 1}
        : <String, dynamic>{
            'query': query.text.trim(),
            'profile': profile.text.trim(),
            'mode': mode,
            'work_mode': work,
            'countries': country.isEmpty ? <String>[] : [country],
            'sources': source.isEmpty ? <String>[] : [source],
            'job_type': jobType,
            'page': 1,
            'page_size': 8,
          };
    setState(() {
      busy = true;
      error = null;
      showSaved = false;
      if (!more) {
        jobs = [];
        searched = false;
      }
    });
    try {
      final response = await widget.client
          .post(
            Uri.parse('$apiBase/api/v1/search'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(request),
          )
          .timeout(const Duration(seconds: 30));
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode != 200) {
        throw Exception(data['error'] ?? 'Search failed');
      }
      if (!mounted) {
        return;
      }
      final rows = (data['results'] as List)
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
      setState(() {
        jobs = more ? [...jobs, ...rows] : rows;
        page = data['page'];
        total = data['total_count'];
        hasMore = data['has_more'];
        submitted = request;
        searched = true;
      });
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString().replaceFirst('Exception: ', ''));
      }
    } finally {
      if (mounted) {
        setState(() => busy = false);
      }
    }
  }

  Future<void> toggleSave(Map<String, dynamic> job) async {
    setState(() {
      if (saved.any((j) => j['id'] == job['id'])) {
        saved.removeWhere((j) => j['id'] == job['id']);
      } else {
        saved.add(job);
      }
    });
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('nextrole_saved', jsonEncode(saved));
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not persist saved jobs on this device.');
      }
    }
  }

  Widget choice(
    String label,
    String value,
    List<String> options,
    void Function(String) change,
  ) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: DropdownButtonFormField<String>(
      initialValue: value,
      isExpanded: true,
      decoration: InputDecoration(labelText: label),
      items: ['', ...options]
          .map(
            (v) => DropdownMenuItem(
              value: v,
              child: Text(
                v.isEmpty ? t('Any / unspecified', 'الكل / غير محدد') : v,
              ),
            ),
          )
          .toList(),
      onChanged: busy ? null : (v) => setState(() => change(v ?? '')),
    ),
  );
  Future<void> details(Map<String, dynamic> j) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (context) => Directionality(
        textDirection: arabic ? TextDirection.rtl : TextDirection.ltr,
        child: DraggableScrollableSheet(
          initialChildSize: .8,
          expand: false,
          builder: (context, controller) => ListView(
            controller: controller,
            padding: const EdgeInsets.all(24),
            children: [
              Align(
                alignment: Alignment.topRight,
                child: IconButton(
                  tooltip: 'Close details',
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close),
                ),
              ),
              Text(j['company'], style: const TextStyle(color: green)),
              const SizedBox(height: 8),
              Text(
                j['title'],
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              Text('${j['location']} · ${j['source']}'),
              const SizedBox(height: 22),
              Text(
                t('Why this role appeared', 'سبب ظهور هذه الوظيفة'),
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              Text(j['explanation'] ?? ''),
              Text(
                'Score: ${(j['score'] as num).toStringAsFixed(3)} · ${j['match_type']}',
              ),
              const SizedBox(height: 18),
              Text(
                t('Skills mentioned in your text', 'مهارات مذكورة في نصك'),
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              Text(
                (j['matched_skills'] as List).isEmpty
                    ? 'No explicit overlap detected.'
                    : (j['matched_skills'] as List).join(', '),
              ),
              const SizedBox(height: 16),
              Text(
                t('Skills to check', 'مهارات للتحقق منها'),
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              Text((j['missing_skills'] as List).join(', ')),
              const SizedBox(height: 16),
              const Text(
                'Text overlap is not an assessment of ability. Similarity is not hiring probability.',
              ),
              const Divider(height: 32),
              Text(j['description']),
              if (Uri.tryParse(j['url'] ?? '')?.scheme == 'https')
                Padding(
                  padding: const EdgeInsets.only(top: 20),
                  child: FilledButton.icon(
                    onPressed: () async {
                      final ok = await launchUrl(
                        Uri.parse(j['url']),
                        mode: LaunchMode.externalApplication,
                      );
                      if (!ok && mounted) {
                        setState(
                          () => error = 'Could not open the original vacancy.',
                        );
                      }
                    },
                    icon: const Icon(Icons.open_in_new),
                    label: Text(
                      t('View original vacancy', 'عرض الوظيفة الأصلية'),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget card(Map<String, dynamic> j) => Card(
    margin: const EdgeInsets.only(bottom: 14),
    color: Colors.white,
    elevation: 0,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
      side: const BorderSide(color: Color(0xffd7ddd5)),
    ),
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(j['company'], style: const TextStyle(color: green)),
              ),
              IconButton(
                tooltip:
                    '${saved.any((v) => v['id'] == j['id']) ? 'Unsave' : 'Save'} ${j['title']}',
                onPressed: () => toggleSave(j),
                icon: Icon(
                  saved.any((v) => v['id'] == j['id'])
                      ? Icons.bookmark
                      : Icons.bookmark_outline,
                ),
              ),
            ],
          ),
          Text(
            j['title'],
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w600,
              color: ink,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '${j['location']} · ${j['work_mode'].toString().isEmpty ? 'Unspecified work style' : j['work_mode']}',
          ),
          const SizedBox(height: 8),
          Text(j['source'], style: const TextStyle(fontSize: 12)),
          const Divider(height: 25),
          Row(
            children: [
              Expanded(
                child: Text(
                  j['match_type'] == 'exact'
                      ? t('Exact title match', 'تطابق المسمى')
                      : t('Semantic similarity', 'تشابه دلالي'),
                ),
              ),
              Text(
                (j['score'] as num).toStringAsFixed(2),
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ],
          ),
          TextButton(
            onPressed: () => details(j),
            child: Text(t('Why this role? ↗', 'لماذا هذه الوظيفة؟ ↗')),
          ),
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final rows = showSaved ? saved : jobs;
    return Directionality(
      textDirection: arabic ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: const Color(0xfff7f8f3),
          title: const Text(
            'N↗  NextRole',
            style: TextStyle(fontWeight: FontWeight.bold, color: ink),
          ),
          actions: [
            TextButton(
              onPressed: () => setState(() => arabic = !arabic),
              child: Text(arabic ? 'English' : 'العربية'),
            ),
          ],
        ),
        bottomNavigationBar: NavigationBar(
          selectedIndex: showSaved ? 1 : 0,
          onDestinationSelected: (v) => setState(() => showSaved = v == 1),
          destinations: [
            NavigationDestination(
              icon: const Icon(Icons.explore_outlined),
              label: t('Discover', 'اكتشف'),
            ),
            NavigationDestination(
              icon: const Icon(Icons.bookmark_outline),
              label: '${t('Saved', 'المحفوظة')} (${saved.length})',
            ),
          ],
        ),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(22),
            children: [
              if (!showSaved) ...[
                Text(
                  t('YOUR NEXT CHAPTER', 'خطوتك المهنية القادمة'),
                  style: const TextStyle(
                    fontSize: 11,
                    letterSpacing: 1.5,
                    color: green,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  t(
                    'Good work starts with\nthe right match.',
                    'الفرصة المناسبة تبدأ\nبالتوافق المناسب.',
                  ),
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 12),
                Text(
                  t(
                    'Your skills. Your preferences. Every recommendation explained.',
                    'مهاراتك وتفضيلاتك مع تفسير لكل توصية.',
                  ),
                ),
                const SizedBox(height: 22),
                TextField(
                  controller: query,
                  maxLength: 200,
                  decoration: InputDecoration(
                    labelText: t('Role or skills', 'المسمى أو المهارات'),
                    hintText: 'Flutter Developer',
                    counterText: '',
                  ),
                  onSubmitted: (_) => search(),
                ),
                const SizedBox(height: 12),
                ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: Text(
                    t(
                      'Preferences and candidate context',
                      'التفضيلات والخبرات',
                    ),
                  ),
                  children: [
                    TextField(
                      controller: profile,
                      maxLength: 6000,
                      maxLines: 3,
                      decoration: InputDecoration(
                        labelText: t(
                          'Skills and experience (optional)',
                          'المهارات والخبرات (اختياري)',
                        ),
                      ),
                    ),
                    const Padding(
                      padding: EdgeInsets.only(bottom: 12),
                      child: Text(
                        'Omit contact details. Candidate text is processed locally per request and is not saved by the API. Long text is truncated.',
                      ),
                    ),
                    choice(t('Work style', 'نمط العمل'), work, [
                      'remote',
                      'hybrid',
                      'onsite',
                    ], (v) => work = v),
                    choice(t('Job type', 'نوع الوظيفة'), jobType, [
                      'full_time',
                      'part_time',
                      'contract',
                      'internship',
                    ], (v) => jobType = v),
                    choice(
                      t('Country', 'الدولة'),
                      country,
                      countries,
                      (v) => country = v,
                    ),
                    choice(
                      t('Source', 'المصدر'),
                      source,
                      sources,
                      (v) => source = v,
                    ),
                    DropdownButtonFormField<String>(
                      initialValue: mode,
                      decoration: InputDecoration(
                        labelText: t('Ranking strategy', 'طريقة الترتيب'),
                      ),
                      items: ['hybrid', 'exact', 'semantic']
                          .map(
                            (v) => DropdownMenuItem(value: v, child: Text(v)),
                          )
                          .toList(),
                      onChanged: busy ? null : (v) => setState(() => mode = v!),
                    ),
                    const SizedBox(height: 12),
                  ],
                ),
                FilledButton(
                  onPressed: busy ? null : () => search(),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(t('Find my next role ↗', 'ابحث عن فرصتي ↗')),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  dataset == 'synthetic-functional-fixtures'
                      ? 'Demonstration · fictional vacancies'
                      : '$dataset · ${sources.join(' + ')}',
                  style: const TextStyle(fontSize: 11),
                ),
                const SizedBox(height: 18),
              ],
              if (error != null)
                Semantics(
                  liveRegion: true,
                  child: Card(
                    color: const Color(0xffffeee9),
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        children: [
                          Text(error!),
                          TextButton(
                            onPressed: busy ? null : () => search(),
                            child: const Text('Retry search'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              if (busy)
                Semantics(
                  label: 'Searching',
                  liveRegion: true,
                  child: LinearProgressIndicator(),
                ),
              const SizedBox(height: 12),
              Text(
                showSaved
                    ? t('Your shortlist', 'قائمتك المختصرة')
                    : '${t('Opportunities', 'الفرص')} ${searched ? '($total)' : ''}',
                style: const TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 12),
              if (rows.isEmpty && !busy)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  child: Text(
                    showSaved
                        ? t(
                            'Save a role to compare it later on this device.',
                            'احفظ وظيفة لمقارنتها لاحقاً.',
                          )
                        : searched
                        ? t(
                            'No matches. Try a broader role or remove a filter.',
                            'لا توجد نتائج. جرّب مسمى أوسع أو أزل مرشحاً.',
                          )
                        : t(
                            'Start with a role to explore your next chapter.',
                            'ابدأ بمسمى وظيفي لاستكشاف فرصك.',
                          ),
                  ),
                ),
              ...rows.map(card),
              if (hasMore && !showSaved)
                OutlinedButton(
                  onPressed: busy ? null : () => search(more: true),
                  child: Text(t('Load more opportunities', 'تحميل المزيد')),
                ),
              const SizedBox(height: 18),
              Text(
                t(
                  'Similarity is not hiring probability. NextRole uses explicit preferences, without behavioural tracking.',
                  'التشابه ليس احتمال التوظيف. تستخدم NextRole تفضيلاتك دون تتبع سلوكي.',
                ),
                style: const TextStyle(fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

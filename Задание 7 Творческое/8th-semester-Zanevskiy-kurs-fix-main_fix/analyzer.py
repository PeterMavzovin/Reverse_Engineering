from __future__ import division
from __future__ import print_function
import sys
import re
import string
import os

filename = ""
linenumber = 0
sumlines = 0
sloc = 0

def error(message):
    sys.stderr.write("Error: %s\n" % message)

def print_multi_line(text):
    width = 500
    prefix = " "
    starting_position = len(prefix) + 1

    print(prefix, end='')
    position = starting_position

    for w in text.split():
        if len(w) + position >= width:
            print()
            print(prefix, end='')
            position = starting_position
        print(' ', end='')
        print(w, end='')
        position += len(w) + 1

class Hit(object):
    source_position = 2
    format_position = 1
    input = 0
    note = ""
    filename = ""
    extract_lookahead = 0

    def __init__(self, data):
        hook, warning, suggestion, category, url, other = data
        self.hook = hook
        self.warning, self.suggestion = warning, suggestion
        self.category, self.url = category, url
        self.line = 0
        self.name = ""
        self.context_text = ""
        for key in other:
            setattr(self, key, other[key])

    def __getitem__(self, X):
        return getattr(self, X)

    def __eq__(self, other):
        return (self.filename == other.filename
                and self.line == other.line
                and self.name == other.name)

    def __ne__(self, other):
        return not self == other

    def show(self):
        sys.stdout.write(self.filename)

        print(":%(line)s:" % self, end='')
        print("(%(category)s)" % self, end=' ')
        print("%(name)s:" % self, end='')
        main_text = "%(warning)s. " % self
        if self.suggestion:
            main_text += self.suggestion + ". "
        main_text += self.note
        print()
        print_multi_line(main_text)
        print()

hitlist = []

def add_warning(hit):
    global hitlist
    hitlist.append(hit)

def internal_warn(message):
    print(message, file=sys.stderr)

def extract_c_parameters(text, pos=0):
    "Возвращает список параметров данной функции C, начиная с text[pos]"

    i = pos

    while i < len(text):
        if text[i] == '(':
            break
        elif text[i] in string.whitespace:
            i += 1
        else:
            return []
    else:
        return []
    i += 1
    parameters = [""]
    currentstart = i
    parenlevel = 1
    curlylevel = 0
    instring = 0
    incomment = 0
    while i < len(text):
        c = text[i]
        if instring:
            if c == '"' and instring == 1:
                instring = 0
            elif c == "'" and instring == 2:
                instring = 0
            elif c == '\\':
                i += 1
        elif incomment:
            if c == '*' and text[i:i + 2] == '*/':
                incomment = 0
                i += 1
        else:
            if c == '"':
                instring = 1
            elif c == "'":
                instring = 2
            elif c == '/' and text[i:i + 2] == '/*':
                incomment = 1
                i += 1
            elif c == '/' and text[i:i + 2] == '//':
                while i < len(text) and text[i] != "\n":
                    i += 1
            elif c == '\\' and text[i:i + 2] == '\\"':
                i += 1
            elif c == '(':
                parenlevel += 1
            elif c == ',' and (parenlevel == 1):
                parameters.append(
                    p_trailingbackslashes.sub('', text[currentstart:i]).strip())
                currentstart = i + 1
            elif c == ')':
                parenlevel -= 1
                if parenlevel <= 0:
                    parameters.append(
                        p_trailingbackslashes.sub(
                            '', text[currentstart:i]).strip())
                    return parameters
            elif c == '{':
                curlylevel += 1
            elif c == '}':
                curlylevel -= 1
            elif c == ';' and curlylevel < 1:
                internal_warn(
                    "При синтаксическом анализе не удалось найти конец списка параметров; "
                    "точка с запятой заканчивалась в %s" % text[pos:pos + 200])
                return parameters
        i += 1
    internal_warn("При синтаксическом анализе не удалось найти конец списка параметров в %s" %
                  text[pos:pos + 200])
    return []

gettext_pattern = re.compile(r'(?s)^\s*' 'gettext' r'\s*\((.*)\)\s*$')
undersc_pattern = re.compile(r'(?s)^\s*' '_(T(EXT)?)?' r'\s*\((.*)\)\s*$')

def strip_i18n(text):
    match = gettext_pattern.search(text)
    if match:
        return match.group(1).strip()
    match = undersc_pattern.search(text)
    if match:
        return match.group(3).strip()
    return text


p_trailingbackslashes = re.compile(r'(\s|\\(\n|\r))*$')

p_c_singleton_string = re.compile(r'^\s*L?"([^\\]|\\[^0-6]|\\[0-6]+)?"\s*$')


def c_singleton_string(text):
    "Возвращает true, если текст представляет собой строку C с 0 или 1 символом."
    return 1 if p_c_singleton_string.search(text) else 0


p_c_constant_string = re.compile(r'^\s*L?"([^\\]|\\[^0-6]|\\[0-6]+)*"$')


def c_constant_string(text):
    "Возвращает true, если текст является константной строкой C."
    return 1 if p_c_constant_string.search(text) else 0


p_memcpy_sizeof = re.compile(r'sizeof\s*\(\s*([^)\s]*)\s*\)')
p_memcpy_param_amp = re.compile(r'&?\s*(.*)')


def c_memcpy(hit):
    if len(hit.parameters) < 4:
        add_warning(hit)
        return

    m1 = re.search(p_memcpy_param_amp, hit.parameters[1])
    m3 = re.search(p_memcpy_sizeof, hit.parameters[3])
    if not m1 or not m3 or m1.group(1) != m3.group(1):
        add_warning(hit)


def c_buffer(hit):
    source_position = hit.source_position
    if source_position <= len(hit.parameters) - 1:
        source = hit.parameters[source_position]
        if c_singleton_string(source):
            hit.note = "Риск низкий, потому что источник является константным символом."
        elif c_constant_string(strip_i18n(source)):
            hit.note = "Риск низкий, потому что источником является константной строкой."
    add_warning(hit)

def c_printf(hit):
    format_position = hit.format_position
    if format_position <= len(hit.parameters) - 1:
        source = strip_i18n(hit.parameters[format_position])
        if c_constant_string(source):
            hit.note = "Строка постоянного формата, поэтому не считается рискованной."
    add_warning(hit)

p_dangerous_sprintf_format = re.compile(r'%-?([0-9]+|\*)?s')


def c_sprintf(hit):
    source_position = hit.source_position
    if hit.parameters is None:

        hit.warning = "проблема с параметром формата строки"
        hit.suggestion = "Проверить наличие требуемых параметров и закрытия кавычек."
        hit.category = "format"
        hit.url = ""
    elif source_position <= len(hit.parameters) - 1:
        source = hit.parameters[source_position]
        if c_singleton_string(source):
            hit.note = "Риск низкий, потому что источник является постоянным символом."
        else:
            source = strip_i18n(source)
            if c_constant_string(source):
                if not p_dangerous_sprintf_format.search(source):
                    hit.note = "Риск низкий, потому что источник имеет постоянную максимальную длину."

            else:

                hit.warning = "Возможная проблема со строкой формата (CWE-134)"
                hit.suggestion = "Сделайте строку формата постоянной"
                hit.category = "format"
                hit.url = ""
    add_warning(hit)

p_dangerous_scanf_format = re.compile(r'%s')
p_low_risk_scanf_format = re.compile(r'%[0-9]+s')


def c_scanf(hit):
    format_position = hit.format_position
    if format_position <= len(hit.parameters) - 1:
        source = strip_i18n(hit.parameters[format_position])
        if c_constant_string(source):
            if p_dangerous_scanf_format.search(source):
                pass
            elif p_low_risk_scanf_format.search(source):
                hit.warning = ("Неясно, установлен ли предел в %s  "
                               "строка формата достаточно мала (CWE-120)")
                hit.suggestion = ("Убедитесь, что предел достаточно "
                                  "маленький или используйте другую функцию ввода")
            else:
                hit.note = "Опасный формат scanf не обнаружен."
        else:

            hit.note = ("Если формат scanf подвержен влиянию "
                        "то злоумышленник может воспользоваться этим.")
    add_warning(hit)


p_dangerous_multi_byte = re.compile(r'^\s*sizeof\s*(\(\s*)?[A-Za-z_$0-9]+'
                                    r'\s*(\)\s*)?(-\s*1\s*)?$')
p_safe_multi_byte = re.compile(
    r'^\s*sizeof\s*(\(\s*)?[A-Za-z_$0-9]+\s*(\)\s*)?'
    r'/\s*sizeof\s*\(\s*?[A-Za-z_$0-9]+\s*\[\s*0\s*\]\)\s*(-\s*1\s*)?$')


def c_multi_byte_to_wide_char(hit):
    if len(hit.parameters) - 1 >= 6:
        num_chars_to_copy = hit.parameters[6]
        if p_dangerous_multi_byte.search(num_chars_to_copy):
            hit.note = (
                "Риск высок, кажется, что размер указан в байтах, но "
                "функция требует размер в виде символов.")
        elif p_safe_multi_byte.search(num_chars_to_copy):
            hit.note = "Риск очень низкий, длина указана в символах, а не в байтах."
    add_warning(hit)


p_null_text = re.compile(r'^ *(NULL|0|0x0) *$')


def c_hit_if_null(hit):
    null_position = hit.check_for_null
    if null_position <= len(hit.parameters) - 1:
        null_text = hit.parameters[null_position]
        if p_null_text.search(null_text):
            add_warning(hit)
        else:
            return
    add_warning(hit)


p_static_array = re.compile(r'^[A-Za-z_]+\s+[A-Za-z0-9_$,\s\*()]+\[[^]]')


def c_static_array(hit):
    if p_static_array.search(hit.lookahead):
        add_warning(hit)


def cpp_unsafe_stl(hit):
    if len(hit.parameters) <= 4:
        add_warning(hit)

def normal(hit):
    add_warning(hit)


c_ruleset = {
    "strcpy":
        (c_buffer,
         "Не проверяет переполнение буфера при копировании в место назначения [Запрещенная Майкрософтом функция] (CWE-120)",
         "Рассмотрите возможность использования snprintf, strcpy_s, или strlcpy",
         "buffer", "", {}),

    "strcpyA|strcpyW|StrCpy|StrCpyA|lstrcpyA|lstrcpyW|_tccpy|_mbccpy|_ftcscpy|_mbsncpy|StrCpyN|StrCpyNA|StrCpyNW|StrNCpy|strcpynA|StrNCpyA|StrNCpyW|lstrcpynA|lstrcpynW":
        (normal,
         "Не проверяет переполнение буфера при копировании в место назначения [Запрещенная Майкрософтом функция] (CWE-120)",
         "Рассмотрите возможность использования snprintf, strcpy_s, или strlcpy",
         "buffer", "", {}),

    "lstrcpy|wcscpy|_tcscpy|_mbscpy":
        (c_buffer,
         "Не проверяет переполнение буфера при копировании в место назначения [Запрещенная Майкрософтом функция] (CWE-120)",
         "Рассмотрите возможность использования версии функции, которая останавливает копирование в конце буфера.",
         "buffer", "", {}),

    "memcpy|CopyMemory|bcopy":
        (c_memcpy,
         "Не проверяет переполнение буфера при копировании в место назначения (CWE-120)",
         "Убедитесь, что пункт назначения всегда может содержать исходные данные",
         "buffer", "", {}),

    "strcat":
        (c_buffer,
         "Не проверяет переполнение буфера при объединении в пункт назначения [Запрещенная Майкрософтом функция] (CWE-120)",
         "Рассмотрите возможность использования strcat_s, strncat, strlcat или snprintf",
         "buffer", "", {}),

    "lstrcat|wcscat|_tcscat|_mbscat":
        (c_buffer,
         "Не проверяет переполнение буфера при объединении в пункт назначения [Запрещенная Майкрософтом функция] (CWE-120)",
         "",
         "buffer", "", {}),

    "StrCat|StrCatA|StrcatW|lstrcatA|lstrcatW|strCatBuff|StrCatBuffA|StrCatBuffW|StrCatChainW|_tccat|_mbccat|_ftcscat|StrCatN|StrCatNA|StrCatNW|StrNCat|StrNCatA|StrNCatW|lstrncat|lstrcatnA|lstrcatnW":
        (normal,
         "Не проверяет переполнение буфера при объединении в пункт назначения [Запрещенная Майкрософтом функция] (CWE-120)",
         "",
         "buffer", "", {}),

    "strncpy":
        (c_buffer,
         "Easily used incorrectly; doesn't always \\0-terminate or "
         "check for invalid pointers [Запрещенная Майкрософтом функция] (CWE-120)",
         "",
         "buffer", "", {}),

    "strncat":
        (c_buffer,
         "Легко использовать неправильно (например, неправильно рассчитать правильный максимальный размер для добавления) [Запрещенная Майкрософтом функция] (CWE-120)",
         "Рассмотрите strcat_s, strlcat, snprintf или автоматическое изменение размера строк.",
         "buffer", "", {}),

    "lstrcatn|wcsncat|_tcsncat|_mbsnbcat":
        (c_buffer,
         "Легко использовать неправильно (например, неправильно рассчитать правильный максимальный размер для добавления) [Запрещенная Майкрософтом функция] (CWE-120)",
         "Рассмотрите strcat_s, strlcat или автоматическое изменение размера строк.",
         "buffer", "", {}),

    "strccpy|strcadd":
        (normal,
         "Возможно переполнение буфера, если буфер не такой большой, как заявлено(CWE-120)",
         "Убедитесь, что буфер назначения достаточно велик",
         "buffer", "", {}),

    "char|TCHAR|wchar_t":
        (c_static_array,
         "Массивы статического размера могут быть неправильно ограничены, "
         "что приводит к потенциальным переполнениям или другим проблемам (CWE-119!/CWE-120)",
         "Выполните проверку границ, используйте функции, ограничивающие длину, "
         "или убедитесь, что размер больше максимально возможной длины",
         "buffer", "", {'extract_lookahead': 1}),

    "gets|_getts":
        (normal, "Не проверяет переполнение буфера (CWE-120, CWE-20)",
         "Используйте fgets() instead", "buffer", "", {'input': 1}),

    "sprintf|vsprintf|swprintf|vswprintf|_stprintf|_vstprintf":
        (c_sprintf,
         "Не проверяет переполнение буфера (CWE-120)",
         "Используйте sprintf_s, snprintf, or vsnprintf",
         "buffer", "", {}),

    "printf|vprintf|vwprintf|vfwprintf|_vtprintf|wprintf":
        (c_printf,
         "Если злоумышленник может повлиять на строки формата, они могут быть проэксплуатированы (CWE-134)",
         "Используйте константу для спецификации формата",
         "format", "", {}),

    "fprintf|vfprintf|_ftprintf|_vftprintf|fwprintf|fvwprintf":
        (c_printf,
         "Если злоумышленник может повлиять на строки формата, они могут быть проэксплуатированы (CWE-134)",
         "Используйте константу для спецификации формата",
         "format", "", {'format_position': 2}),

    "syslog":
        (c_printf,
         "Если злоумышленник может повлиять на строки формата системного журнала, "
         "они могут служить эксплоитом (CWE-134)",
         "Используйте строку постоянного формата для syslog",
         "format", "", {'format_position': 2}),


    "scanf|vscanf|wscanf|_tscanf|vwscanf":
        (c_scanf,
         "Операция %s семейства scanf() без указания предела, "
         "разрешает переполнение буфера (CWE-120, CWE-20)",
         "Укажите предел до %s или используйте другую функцию ввода",
         "buffer", "", {'input': 1}),

    "fscanf|sscanf|vsscanf|vfscanf|_ftscanf|fwscanf|vfwscanf|vswscanf":
        (c_scanf,
         "Операция %s семейства scanf() без указания предела, "
         "разрешает переполнение буфера (CWE-120, CWE-20)",
         "Укажите предел до %s или используйте другую функцию ввода",
         "buffer", "", {'input': 1, 'format_position': 2}),

    "getchar|fgetc|getc|read|_gettc":
        (normal,
         "Проверяйте границы буфера, если он состоит из цикла, включая рекурсивные циклы. (CWE-120, CWE-20)",
         "",
         "buffer", "dangers-c", {'input': 1}),


    "fopen|open":
        (normal,
         "Проверяйте при открытии файлов, может ли злоумышленник перенаправить их (через символические ссылки), принудительно открыть файлы особого типа (например, файлы устройств), перемещать объекты для создания условий гонки, контролировать их предков или изменять их содержимое? (CWE-362)",
         "",
         "misc", "", {}),


    "CreateProcess":
        (c_hit_if_null,
         "Это приводит к выполнению нового процесса, и его трудно безопасно использовать. (CWE-78)",
         "Укажите путь к приложению в первом аргументе, а НЕ как часть второго, "
         "или встроенные пробелы могут позволить злоумышленнику принудительно запустить другую программу",
         "shell", "", {'check_for_null': 1}),

    "atoi|atol|_wtoi|_wtoi64":
        (normal,
         "Если флажок не установлен, результирующее число может превышать ожидаемый диапазон. "
         "(CWE-190)",
         "Если источник ненадежен, проверьте как минимум, так и максимум, даже если"
         " ввод не имел знака минус (большие числа могут превращаться в отрицательные"
         " количество; рассмотрите возможность сохранения беззнакового значения, если это предназначено)",
         "integer", "dangers-c", {}),

    "crypt|crypt_r":
        (normal,
         "Функции шифрования используют плохой алгоритм одностороннего хеширования.; "
         "так как они принимают только пароли из 8 символов или меньше "
         "и только двухбайтная соль, они чрезмерно уязвимы для "
         "атаки по словарю с учетом современного более быстрого вычислительного оборудования (CWE-327)",
         "использовать другой алгоритм, такой как SHA-256, с большим, "
         "неповторяющайся соли",
         "crypto", "", {}),



    "LoadLibrary":
        (normal,
         "Убедитесь, что указан полный путь к библиотеке, иначе можно использовать текущий каталог (CWE-829, CWE-20)",
         "Используйте LoadLibraryEx с одним из флагов поиска, или вызовите SetSearchPathMode, чтобы создать безопасный путь поиска, или передайте полный путь к библиотеке",
         "misc", "", {'input': 1}),


    "SetSecurityDescriptorDacl":
        (c_hit_if_null,
         "Никогда не создавайте NULL ACL; злоумышленник может установить его для всех (запретить всем доступ), "
         "что даже запретит доступ администратора (CWE-732)",
         "",
         "misc", "", {'check_for_null': 3}),

    "ulimit":
        (normal,
         "Эта процедура C считается устаревшей (в отличие от одноименной команды оболочки, которая НЕ является устаревшей) (CWE-676)",
         "Используйте getrlimit(2), setrlimit(2), and sysconf(3) взамен их",
         "obsolete", "", {}),

    "usleep":
        (normal,
         "Эта процедура C считается устаревшей (в отличие от одноименной команды оболочки). Взаимодействие этой функции с SIGALRM и другими функциями таймера, такими как sleep(), alarm(), setitimer() и nanosleep(), не указано. (CWE-676)",
         "Используйте nanosleep(2) or setitimer(2) взамен их",
         "obsolete", "", {}),

    "recv|recvfrom|recvmsg|fread|readv":
        (normal, "Функция принимает ввод из внешней программы (CWE-20)",
         "Убедитесь, что входные данные отфильтрованы, особенно если злоумышленник может ими манипулировать.",
         "input", "", {'input': 1}),

    "equal|mismatch|is_permutation":
        (cpp_unsafe_stl,
         "Функция не проверяет второй итератор на наличие условий перечитания(CWE-126)",
         "Эта функция часто не рекомендуется большинством стандартов кодирования C++ в пользу ее более безопасных альтернатив, представленных начиная с C++14. Рассмотрите возможность использования формы этой функции, которая проверяет второй итератор, прежде чем он может переполниться.",
         "buffer", "", {}),
}


def get_context(text, position):
    "Получить окружающую текстовую строку, начинающуюся с text[position]"
    linestart = text.rfind("\n", 0, position + 1) + 1
    lineend = text.find("\n", position, len(text))
    if lineend == -1:
        lineend = len(text)
    return text[linestart:lineend]


p_whitespace = re.compile(r'[ \t\v\f]+')
p_include = re.compile(r'#\s*include\s+(<.*?>|".*?")')
p_digits = re.compile(r'[0-9]')


p_c_word = re.compile(r'[A-Za-z_][A-Za-z_0-9$]*')

max_lookahead = 500

def process_c_file(f, patch_infos):
    global filename, linenumber, sumlines
    global sloc
    filename = f

    cpplanguage = (f.endswith(".cpp") or f.endswith(".cxx") or f.endswith(".cc")
                   or f.endswith(".hpp"))
    incomment = 0
    instring = 0
    linebegin = 1
    codeinline = 0

    if (patch_infos is not None) and (f not in patch_infos):
        return

    if f == "-":
        my_input = sys.stdin
    else:
        try:
            my_input = open(f, "r")
        except BaseException:
            print("Error: failed to open", f)
            sys.exit(14)
    i = 0
    text = my_input.read()
    while i < len(text):
        m = p_whitespace.match(text, i)
        if m:
            i = m.end(0)

        if i >= len(text):
            c = "\n"
        else:
            c = text[i]
        if linebegin:
            linebegin = 0
            if c == "#":
                codeinline = 1
            m = p_include.match(text, i)
            if m:
                i = m.end(0)
                continue
        if c == "\n":
            linenumber += 1
            sumlines += 1
            linebegin = 1
            if codeinline:
                sloc += 1
            codeinline = 0
            i += 1
            continue
        i += 1
        if i < len(text):
            nextc = text[i]
        else:
            nextc = ''
        if incomment:
            if c == '*' and nextc == '/':
                i += 1
                incomment = 0
        elif instring:
            if c == '\\' and (nextc != "\n"):
                i += 1
            elif c == '"' and instring == 1:
                instring = 0
            elif c == "'" and instring == 2:
                instring = 0
        else:
            if c == '/' and nextc == '*':
                i += 1
                incomment = 1
            elif c == '/' and nextc == '/':
                while i < len(text) and text[i] != "\n":
                    i += 1
            elif c == '"':
                instring = 1
                codeinline = 1
            elif c == "'":
                instring = 2
                codeinline = 1
            else:
                codeinline = 1
                m = p_c_word.match(text, i - 1)
                if m:
                    startpos = i - 1
                    endpos = m.end(0)
                    i = endpos
                    word = text[startpos:endpos]

                    if (word in c_ruleset):
                        if ((patch_infos is None)
                                or ((patch_infos is not None) and
                                    (linenumber in patch_infos[f]))):
                            hit = Hit(c_ruleset[word])
                            hit.name = word
                            hit.start = startpos
                            hit.end = endpos
                            hit.line = linenumber
                            hit.filename = filename
                            hit.context_text = get_context(text, startpos)
                            hit.parameters = extract_c_parameters(text, endpos)
                            if hit.extract_lookahead:
                                hit.lookahead = text[startpos:
                                                     startpos + max_lookahead]
                            hit.hook(hit)
                elif p_digits.match(c):
                    while i < len(text):

                        if p_digits.match(text[i]) or (cpplanguage and text[i] == "'"):
                            i += 1
                        else:
                            break

    if codeinline:
        sloc += 1


def expand_ruleset(ruleset):
    for rule in list(ruleset.keys()):
        if "|" in rule:
            for newrule in rule.split("|"):
                ruleset[newrule] = ruleset[rule]
            del ruleset[rule]

def maybe_process_file(f, patch_infos):
    if os.path.isdir(f):
        base_filename = os.path.basename(f)
        for dir_entry in os.listdir(f):
            maybe_process_file(os.path.join(f, dir_entry), patch_infos)
    dotposition = f.rfind(".")
    if dotposition > 1:
        extension = f[dotposition:]
        if ((patch_infos is None)
                or (patch_infos is not None and (f in patch_infos))):
            process_c_file(f, patch_infos)

def process_file_args(files, patch_infos):
    for f in files:
        if os.path.isfile(f):
            if ((patch_infos is not None and f in patch_infos)
                    or (patch_infos is None)):
                process_c_file(f, patch_infos)
        elif os.path.isdir(f):
            maybe_process_file(f, patch_infos)

def process_files(files = None):
    patch_infos = None
    if files == None:
        files = sys.argv[1:]
    else:
        files = [files]
    if not files:
        print("*** No input files")
        return None
    process_file_args(files, patch_infos)
    return True

def hitlist_sort_key(hit):
    return (hit.filename, hit.line, hit.name)

def show_final_results():
    global hitlist
    count = 0
    hitlist.sort(key=hitlist_sort_key)
    for hit in hitlist:
        hit.show()
        count += 1
    print()
    print("Проанализированно суммарно:")
    print()
    if count > 0:
        print("Попаданий =", count)
    else:
        print("Уязвимости не найдены.")
    print("Количество проанализированных строк = %d" % sumlines, end='')
    print()
    print("Количество строк с исходным кодом = %d" % sloc)
    print()

def analyze(filename = None):
    expand_ruleset(c_ruleset)
    if process_files(filename):
        show_final_results()
    return 0

def main():
    analyze()

if __name__ == '__main__':
    main()

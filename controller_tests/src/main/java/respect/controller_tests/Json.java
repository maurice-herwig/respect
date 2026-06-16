package respect.controller_tests;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class Json {
    private Json() {
    }

    // Minimal JSON support keeps the test runner buildable without external dependencies.
    public static Object parse(String text) {
        return new Parser(text).parse();
    }

    public static String stringify(Object value) {
        StringBuilder out = new StringBuilder();
        write(value, out);
        return out.toString();
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> asObject(Object value, String label) {
        if (value instanceof Map<?, ?>) {
            return (Map<String, Object>) value;
        }
        throw new IllegalArgumentException(label + " must be a JSON object");
    }

    @SuppressWarnings("unchecked")
    public static List<Object> asArray(Object value, String label) {
        if (value instanceof List<?>) {
            return (List<Object>) value;
        }
        throw new IllegalArgumentException(label + " must be a JSON array");
    }

    private static void write(Object value, StringBuilder out) {
        if (value == null) {
            out.append("null");
        } else if (value instanceof String) {
            writeString((String) value, out);
        } else if (value instanceof Number || value instanceof Boolean) {
            out.append(value);
        } else if (value instanceof Map<?, ?>) {
            out.append('{');
            boolean first = true;
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                writeString(String.valueOf(entry.getKey()), out);
                out.append(':');
                write(entry.getValue(), out);
            }
            out.append('}');
        } else if (value instanceof Iterable<?>) {
            out.append('[');
            boolean first = true;
            for (Object item : (Iterable<?>) value) {
                if (!first) {
                    out.append(',');
                }
                first = false;
                write(item, out);
            }
            out.append(']');
        } else {
            writeString(String.valueOf(value), out);
        }
    }

    private static void writeString(String value, StringBuilder out) {
        out.append('"');
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"':
                    out.append("\\\"");
                    break;
                case '\\':
                    out.append("\\\\");
                    break;
                case '\n':
                    out.append("\\n");
                    break;
                case '\r':
                    out.append("\\r");
                    break;
                case '\t':
                    out.append("\\t");
                    break;
                default:
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
            }
        }
        out.append('"');
    }

    private static final class Parser {
        private final String text;
        private int pos;

        Parser(String text) {
            this.text = text;
        }

        Object parse() {
            Object value = parseValue();
            skipWhitespace();
            if (pos != text.length()) {
                throw error("Unexpected trailing input");
            }
            return value;
        }

        private Object parseValue() {
            skipWhitespace();
            if (pos >= text.length()) {
                throw error("Unexpected end of input");
            }
            char c = text.charAt(pos);
            if (c == '{') {
                return parseObject();
            }
            if (c == '[') {
                return parseArray();
            }
            if (c == '"') {
                return parseString();
            }
            if (c == 't' && text.startsWith("true", pos)) {
                pos += 4;
                return Boolean.TRUE;
            }
            if (c == 'f' && text.startsWith("false", pos)) {
                pos += 5;
                return Boolean.FALSE;
            }
            if (c == 'n' && text.startsWith("null", pos)) {
                pos += 4;
                return null;
            }
            return parseNumber();
        }

        private Map<String, Object> parseObject() {
            expect('{');
            Map<String, Object> object = new LinkedHashMap<>();
            skipWhitespace();
            if (peek('}')) {
                pos++;
                return object;
            }
            while (true) {
                String key = parseString();
                skipWhitespace();
                expect(':');
                object.put(key, parseValue());
                skipWhitespace();
                if (peek('}')) {
                    pos++;
                    return object;
                }
                expect(',');
            }
        }

        private List<Object> parseArray() {
            expect('[');
            List<Object> array = new ArrayList<>();
            skipWhitespace();
            if (peek(']')) {
                pos++;
                return array;
            }
            while (true) {
                array.add(parseValue());
                skipWhitespace();
                if (peek(']')) {
                    pos++;
                    return array;
                }
                expect(',');
            }
        }

        private String parseString() {
            expect('"');
            StringBuilder out = new StringBuilder();
            while (pos < text.length()) {
                char c = text.charAt(pos++);
                if (c == '"') {
                    return out.toString();
                }
                if (c != '\\') {
                    out.append(c);
                    continue;
                }
                if (pos >= text.length()) {
                    throw error("Unterminated escape");
                }
                char esc = text.charAt(pos++);
                switch (esc) {
                    case '"':
                    case '\\':
                    case '/':
                        out.append(esc);
                        break;
                    case 'b':
                        out.append('\b');
                        break;
                    case 'f':
                        out.append('\f');
                        break;
                    case 'n':
                        out.append('\n');
                        break;
                    case 'r':
                        out.append('\r');
                        break;
                    case 't':
                        out.append('\t');
                        break;
                    case 'u':
                        if (pos + 4 > text.length()) {
                            throw error("Invalid unicode escape");
                        }
                        out.append((char) Integer.parseInt(text.substring(pos, pos + 4), 16));
                        pos += 4;
                        break;
                    default:
                        throw error("Invalid escape");
                }
            }
            throw error("Unterminated string");
        }

        private Number parseNumber() {
            int start = pos;
            if (peek('-')) {
                pos++;
            }
            while (pos < text.length() && Character.isDigit(text.charAt(pos))) {
                pos++;
            }
            if (peek('.')) {
                pos++;
                while (pos < text.length() && Character.isDigit(text.charAt(pos))) {
                    pos++;
                }
                return Double.parseDouble(text.substring(start, pos));
            }
            return Long.parseLong(text.substring(start, pos));
        }

        private void skipWhitespace() {
            while (pos < text.length() && Character.isWhitespace(text.charAt(pos))) {
                pos++;
            }
        }

        private boolean peek(char expected) {
            return pos < text.length() && text.charAt(pos) == expected;
        }

        private void expect(char expected) {
            skipWhitespace();
            if (!peek(expected)) {
                throw error("Expected '" + expected + "'");
            }
            pos++;
        }

        private IllegalArgumentException error(String message) {
            return new IllegalArgumentException(message + " at character " + pos);
        }
    }
}

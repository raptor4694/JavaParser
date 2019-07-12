package com.test;

import java.util.*;
import java.util.stream.*;
import java.io.*;

public abstract class Test {
	private static final Set<User> USERS = new HashSet<User>();
	private static final Map<String, Supplier<? extends Animal>> ANIMALS = java.util.Map.of(
		"cat", Cat::new,
		"dog", Dog::new
	);
	private static Scanner keys;
	
	public static void main(String[] args) {
		System.out.println("Hello, world!");
		List<String> strs = java.util.List.of("one", "two", "three", "four", "five", "six", "seven");
		Map<String, Integer> map = java.util.Map.of(
			"one", 1,
			"two", 2,
			"three", 3,
			"four", 4,
			"five", 5,
			"six", 6,
			"seven", 7
		);
		System.out.println("User Database Management System (UDMS) v1.0");
		System.out.println("===========================================");
		try(keys = new Scanner(System.in)) {
			for(;;) {
				String input = input("USERS> ");
				if(input.equalsIgnoreCase("quit")) {
					System.out.println("Goodbye");
					break;
				}
				try {
					doCommand(input);
				} catch(CommandException e) {
					System.out.print("Error: ");
					System.out.println(e.getMessage());
				}
			}
		}
	}
	
	private static void doCommand(String cmd) {
		String[] args = cmd.split("\\s+");
		if(args.length == 0) {
			return;
		}
		switch(args[0].toLowerCase()) {
			case "add" -> {
				String username;
				if(args.length == 1) {
					username = input("Enter a name for the new user: ");
				} else  {
					username = cmd.substring(4).strip();
				}
				if(USERS.stream().filter(user -> user.getName().equalsIgnoreCase(username)).findAny().isPresent()) {
					throw new CommandException("A user by that name already exists");
				}
				var user = new Person(username);
				setupUser(user);
				USERS.add(user);
				System.out.printf("Added %s.\n", user.getName());
			}
			case "remove" -> {
				String username;
				if(args.length == 1) {
					username = input("Enter the user name to remove: ");
				} else  {
					username = cmd.substring(7).strip();
				}
				var users = USERS.stream().filter(user -> user.getName().toLowerCase().contains(username));
				long count = users.count();
				switch(count) {
					case 0 -> {
						System.out.println("There were no users matching your query.");
					}
					case 1 -> {
						var user = users.findAny().get();
						USERS.remove(user);
						System.out.printf("Removed %s.\n", user.getName());
					}
					default -> {
						System.out.printf("There were %d users matching your query.\n", count);
						System.out.println("Which one(s) do you want to remove?");
						ArrayList<User> usersList = users.collect(Collectors.toCollection(ArrayList<User>::new));
						int index = 1;
						for(var user : usersList) {
							System.out.printf(" %d. %s\n", index++, user);
						}
						String[] rangeStrs = input("Enter some indices: ").split("\\s+");
						Range[] ranges = new Range[rangeStrs.length];
						for(int i = 0; i < ranges.length; i++) {
							String rangeStr = rangeStrs[i];
							int idx = rangeStr.indexOf("-");
							try {
								if(idx == -1) {
									ranges[i] = Range.of(Integer.parseUnsignedInt(rangeStr));
								} else  {
									int start = Integer.parseUnsignedInt(rangeStr.substring(0, idx));
									int end = Integer.parseUnsignedInt(rangeStr.substring(idx + 1));
									ranges[i] = Range.of(start, end);
								}
							} catch(NumberFormatException e) {
								throw new CommandException("invalid range '" + rangeStr + "'");
							}
						}
						int removed = 0;
						for(int i = 0; i < usersList.size(); i++) {
							for(var range : ranges) {
								if(range.contains(i)) {
									var user = usersList.get(i);
									USERS.remove(user);
									removed++;
									System.out.printf("Removed %s.\n", user.getName());
									break;
								}
							}
						}
						System.out.printf("Removed %d user(s).\n", removed);
					}
				}
			}
			case "list" -> {
				System.out.println("ALL USERS:");
				for(var user : users) {
					System.out.println(user);
				}
			}
			case "quit" -> {
				checkArgC(args, 0);
				System.out.println("Goodbye");
				System.exit(0);
			}
			default -> throw new CommandException.UnknownCommand(args[0].toLowerCase());
		}
	}
	private static void setupUser(User user) {
		user.setAge(inputUnsignedInt("Enter the user's age: ", -1));
		if(askYesOrNo("Does the user have a home? ")) {
			user.setAddress(inputAddress());
		}
		if(askYesOrNo("Do you want any pets? ")) {
			int count = inputUnsignedInt("How many pets do you want? ");
			for(int i = 0; i < count; i++) {
				user.getPets().add(inputPet());
			}
		}
		System.out.println("User setup complete.");
	}
	private static void modifyUser(User user) {
		final String prompt = "USER \"" + user.getName() + "\"> ";
		System.out.printf("Now modifying user \"%s\". Enter 'done' to finish.\n", user);
		for(;;) {
			String input = input(prompt);
			if(input.equalsIgnoreCase("done")) {
				break;
			}
			try {
				doModifyUserCommand(user, input);
			} catch(CommandException e) {
				System.out.print("Error: ");
				System.out.println(e.getMessage());
			}
		}
	}
	private static void doModifyUserCommand(User user, String cmd) {
		String[] args = cmd.split("\\s+");
		if(args.length == 0) {
			return;
		}
		switch(args[0].toLowerCase()) {
			default -> throw new CommandException.UnknownCommand(args[0].toLowerCase());
		}
	}
	private static Address inputAddress() {
		var builder = Address.builder();
		System.out.println("Address input: for any of the following prompts, enter nothing to skip that field.");
		builder.house(inputEitherUnsignedIntOrString("Enter the house number: ", -1));
		builder.road(input("Enter the road: ", true));
		builder.city(input("Enter the city: ", true));
		builder.state(input("Enter the state: ", true));
		builder.country(input("Enter the country: ", true));
		builder.zipCode(inputUnsignedInt("Enter the zip code: ", -1));
		if(askYesOrNo("Do you want to input additional information? ")) {
			builder.POBox(inputUnsignedInt("Enter the PO Box number: ", -1));
			builder.apartment(inputEitherUnsignedIntOrString("Enter the apartment number: ", -1));
			builder.floor(inputEitherUnsignedIntOrString("Enter the floor number: ", -1));
			builder.suite(inputEitherUnsignedIntOrString("Enter the suite number: ", -1));
			builder.room(inputEitherUnsignedIntOrString("Enter the room number: ", -1));
		}
		return builder.build();
	}
	private static Pet inputPet() {
		String type = input("What type of pet do you want? ");
		var petCreator = ANIMALS.get(type.toLowerCase());
		while(petCreator == null) {
			System.out.printf("Error: unknown animal type \"%s\". Valid animal types are: %s\n", type, ANIMALS.keySet().stream().map(name -> Character.toUpperCase(name.charAt(0)) + name.substring(1)).collect(Collectors.joining(", ")));
			type = input("Try again: ");
			petCreator = ANIMALS.get(type.toLowerCase());
		}
		String name = input("What shall be your " + type.toLowerCase() + "'s name? ");
		return new Pet(petCreator.get(), name);
	}
	private static String input(String prompt) {
		return input(prompt, false);
	}
	private static String input(String prompt, boolean allowEmpty) {
		if(prompt == null) {
			prompt = "";
		}
		if(allowEmpty) {
			try {
				return keys.nextLine().strip();
			} catch(NoSuchElementException e) {
				return "";
			}
		} else  {
			String input;
			do {
				System.out.print(prompt);
				try {
					input = keys.nextLine().strip();
				} catch(NoSuchElementException e) {
				}
			} while(input.isBlank());
			return input;
		}
	}
	private static int inputInt(String prompt) {
		String input = input(prompt);
		for(;;) {
			try {
				return Integer.parseInt(input);
			} catch(NumberFormatException e) {
				System.out.printf("Error: \"%s\" is not a valid integer.\n", input);
				input = input("Try again: ");
			}
		}
	}
	private static int inputInt(String prompt, int defaultValue) {
		String input = input(prompt, true);
		for(;;) {
			if(input.isEmpty()) {
				return defaultValue;
			} else  {
				try {
					return Integer.parseInt(input);
				} catch(NumberFormatException e) {
					System.out.printf("Error: \"%s\" is not a valid integer.\n", input);
					input = input("Try again: ");
				}
			}
		}
	}
	private static int inputUnsignedInt(String prompt) {
		String input = input(prompt);
		for(;;) {
			try {
				return Integer.parseUnsignedInt(input);
			} catch(NumberFormatException e) {
				System.out.printf("Error: \"%s\" is not a valid unsigned integer.\n", input);
				input = input("Try again: ");
			}
		}
	}
	private static int inputUnsignedInt(String prompt, int defaultValue) {
		String input = input(prompt, true);
		for(;;) {
			if(input.isEmpty()) {
				return defaultValue;
			} else  {
				try {
					return Integer.parseUnsignedInt(input);
				} catch(NumberFormatException e) {
					System.out.printf("Error: \"%s\" is not a valid unsigned integer.\n", input);
					input = input("Try again: ");
				}
			}
		}
	}
	private static Either<Integer, String> inputEitherUnsignedIntOrString(String prompt, int defaultValue) {
		String input = input(prompt, true);
		for(;;) {
			if(input.isEmpty()) {
				return Either.first(defaultValue);
			} else  {
				try {
					int value = Integer.parseUnsignedInt(input);
					if(value < 0) {
						System.out.printf("Error: \"%s\" is not a valid unsigned integer.\n", input);
						input = input("Try again: ");
					} else  {
						return Either.first(value);
					}
				} catch(NumberFormatException e) {
					return Either.second(input);
				}
			}
		}
	}
	private static Either<Integer, String> inputEitherUnsignedIntOrString(String prompt, String defaultValue) {
		String input = input(prompt, true);
		for(;;) {
			if(input.isEmpty()) {
				return Either.second(defaultValue);
			} else  {
				try {
					int value = Integer.parseUnsignedInt(input);
					if(value < 0) {
						System.out.printf("Error: \"%s\" is not a valid unsigned integer.\n", input);
						input = input("Try again: ");
					} else  {
						return Either.first(value);
					}
				} catch(NumberFormatException e) {
					return Either.second(input);
				}
			}
		}
	}
	private static OptionalInt inputOptionalInt(String prompt) {
		String input = input(prompt, true);
		for(;;) {
			if(input.isEmpty()) {
				return OptionalInt.empty();
			} else  {
				try {
					return OptionalInt.of(Integer.parseInt(input));
				} catch(NumberFormatException e) {
					System.out.printf("Error: \"%s\" is not a valid integer.\n", input);
					input = input("Try again: ");
				}
			}
		}
	}
	private static OptionalInt inputOptionalUnsignedInt(String prompt) {
		String input = input(prompt, true);
		for(;;) {
			if(input.isEmpty()) {
				return OptionalInt.empty();
			} else  {
				try {
					return OptionalInt.of(Integer.parseUnsignedInt(input));
				} catch(NumberFormatException e) {
					System.out.printf("Error: \"%s\" is not a valid unsigned integer.\n", input);
					input = input("Try again: ");
				}
			}
		}
	}
	private static Optional<String> inputOptional(String prompt) {
		String input = input(prompt, true);
		return input.isEmpty()? Optional.empty() : Optional.of(input);
	}
	private static Optional<Either<Integer, String>> inputOptionalEitherUnsignedIntOrString(String prompt) {
		String input = input(prompt, true);
		for(;;) {
			if(input.isEmpty()) {
				return Optional.empty();
			} else  {
				try {
					int value = Integer.parseUnsignedInt(input);
					if(value < 0) {
						System.out.printf("Error: \"%s\" is not a valid unsigned integer.\n", input);
						input = input("Try again: ");
					} else  {
						return Optional.of(Either.<Integer, String>first(value));
					}
				} catch(NumberFormatException e) {
					return Optional.of(Either.<Integer, String>second(input));
				}
			}
		}
	}
	private static boolean askYesOrNo(String question) {
		String input = input(question);
		while(!input.equalsIgnoreCase("yes") && !input.equalsIgnoreCase("y") && !input.equalsIgnoreCase("no") && !input.equalsIgnoreCase("n")) {
			input = input("You must enter either 'Yes' or 'No': ");
		}
		switch(input.charAt(0)) {
			case "y", "Y":
				return true;
			case "n", "N":
				return false;
			default:
				throw new AssertionError();
		}
	}
	private static void checkArgC(String[] args, int expectedAmount) {
		int length = args.length - 1;
		if(length < expectedAmount) {
			throw new CommandException.TooFewArguments(args[0].toLowerCase(), expectedAmount, length);
		}
		if(length > expectedAmount) {
			throw new CommandException.TooManyArguments(args[0].toLowerCase(), expectedAmount, length);
		}
	}
	private static void checkArgC(String[] args, int minAmount, int maxAmount) {
		int length = args.length - 1;
		if(length < minAmount) {
			throw new CommandException.TooFewArguments(args[0].toLowerCase(), minAmount, length, true);
		}
		if(length > maxAmount) {
			throw new CommandException.TooManyArguments(args[0].toLowerCase(), maxAmount, length, true);
		}
	}
}

class CommandException extends RuntimeException {
	public CommandException(String message) {
		super(message);
	}
		
	public static class TooManyArguments extends CommandException {
		public TooManyArguments(String command) {
			super("too many arguments given to command '" + command + "'");
		}
			
		public TooManyArguments(String command, int expected, int got) {
			this(command, expected, got, false);
		}
			
		public TooManyArguments(String command, int expected, int got, boolean isMaximum) {
			super("too many arguments given to command '" + command + "': expected " + (isMaximum? "a maximum of " : "") + expected + ", got " + got);
		}
	}
	
	public static class TooFewArguments extends CommandException {
		public TooFewArguments(String command) {
			super("not enough arguments given to command '" + command + "'");
		}
			
		public TooFewArguments(String command, int expected, int got) {
			this(command, expected, got, false);
		}
			
		public TooFewArguments(String command, int expected, int got, boolean isMinimum) {
			super("not enough arguments given to command '" + command + "': expected " + (isMinimum? "a minimum of " : "") + expected + ", got " + got);
		}
	}
		
	public static class UnknownCommand extends CommandException {
		public UnknownCommand(String command) {
			super("unknown command '" + command + "'");
		}
	}
}

interface Named {
	String getName();
}

@SuppressWarnings("unchecked")
class Either<F,S> {
	public static <F,S> Either<F,S> first(F first) {
		return new Either<F,S>(true, first);
	}
	
	public static <F,S> Either<F,S> second(S second) {
		return new Either<F,S>(false, second);
	}
	
	private final boolean isFirst;
	private final Object value;
	
	private Either(boolean isFirst, Object value) {
		if(this.isFirst = isFirst) {
			this.value = (F)value;
		} else {
			this.value = (S)value;
		}
	}
	
	public boolean isFirst() { return isFirst; }
	public boolean isSecond() { return !isFirst; }
	
	public F first() {
		if(isFirst) {
			return (F)value;
		} else {
			throw new NoSuchElementException();
		}
	}
	
	public F firstOrElse(F other) {
		return isFirst? (F)value : other;
	}
	
	public F firstOrElseGet(Supplier<? extends F> supplier) {
		return isFirst? (F)value : supplier.get();
	}
	
	public F firstOrElseThrow() {
		if(isFirst) {
			return (F)value;
		} else {
			throw new NoSuchElementException();
		}
	}
	
	public <X extends Throwable> F firstOrElseThrow(Supplier<? extends X> exceptionSupplier) throws X {
		if(isFirst) {
			return (F)value;
		} else {
			throw exceptionSupplier.get();
		}
	}
	
	public S second() {
		if(isFirst) {
			throw new NoSuchElementException();
		} else {
			return (S)value;
		}
	}
	
	public S secondOrElse(S other) {
		return isFirst? other : (S)value;
	}
	
	public S secondOrElseGet(Supplier<? extends S> supplier) {
		return isFirst? supplier.get() : (S)value;
	}
	
	public S secondOrElseThrow() {
		if(isFirst) {
			throw new NoSuchElementException();
		} else {
			return (S)value;
		}
	}
	
	public <X extends Throwable> S secondOrElseThrow(Supplier<? extends X> exceptionSupplier) throws X {
		if(isFirst) {
			throw exceptionSupplier.get();
		} else {
			return (S)value;
		}
	}
	
	public Object get() {
		return value;
	}
	
	public void ifFirst(Consumer<? super F> action) {
		if(isFirst) {
			action.accept((F)value);
		}
	}
	
	public void ifSecond(Consumer<? super S> action) {
		if(!isFirst) {
			action.accept((S)value);
		}
	}
	
	public void ifFirstOrElse(Consumer<? super F> action, Consumer<? super S> otherAction) {
		if(isFirst) {
			action.accept((F)value);
		} else {
			otherAction.accept((S)value);
		}
	}
	
	public void ifSecondOrElse(Consumer<? super S> action, Consumer<? super F> otherAction) {
		if(isFirst) {
			otherAction.accept((F)value);
		} else {
			action.accept((S)value);
		}
	}
	
	public <F2,S2> Either<F2,S2> flatMap(Function<? super F, ? extends Either<? extends F2, ? extends S2>> firstMapper, Function<? super S, ? extends Either<? extends F2, ? extends S2>> secondMapper) {
		return isFirst? (Either<F2,S2>)firstMapper.apply((F)value) : (Either<F2,S2>)secondMapper.apply((S)value);
	}
	
	public <F2,S2> Either<F2,S2> flatMap(BiFunction<? super Boolean, ? super Object, ? extends Either<? extends F2, ? extends S2>> mapper) {
		return (Either<F2,S2>)mapper.apply(isFirst, value);
	}
	
	public <F2,S2> Either<F2,S2> map(BiFunction<? super Boolean, ? super Object, ?> mapper) {
		Object result = mapper.apply(isFirst, value);
		return isFirst? Either.first((F2)result) : Either.second((S2)result);
	}
	
	public int hashCode() {
		return Objects.hash(isFirst, value);
	}
	
	public boolean equals(Object obj) {
		if(this == obj) {
			return true;
		}
		if(obj instanceof Either) {
			var either = (Either<?,?>)obj;
			return isFirst == either.isFirst && Objects.equals(value, either.value);
		}
		return false;
	}
	
	public String toString() {
		return String.format("Either.%s(%s)", isFirst? "first" : "second", value);
	}
}

//#region Range
interface Range extends Iterable<Integer> {
        @Override
        PrimitiveIterator.OfInt iterator();
        boolean contains(int x);
        static Range of(int start, int end) {
                if(start == end) {
                        return EmptyRange.INSTANCE;
                } else if(start == end + 1 || start + 1 == end) {
                        return new SingletonRange(start, end);
                } else if(start < end) {
                        return new ForwardRange(start, end);
                } else  {
                        return new BackwardRange(start, end);
                }
        }
        static Range of(int value) {
                return new SingletonRange(value);
        }
        static Range empty() {
                return EmptyRange.INSTANCE;
        }
        static Range of() {
                return EmptyRange.INSTANCE;
        }
}

class SingletonRange implements Range {
        private final int value;
        public SingletonRange(int value) {
                this.value = value;
        }
        @Override
        public boolean contains(int x) {
                return x == value;
        }
        @Override
        public PrimitiveIterator.OfInt iterator() {
                return new PrimitiveIterator.OfInt() {
                        private boolean hasNext = true;
                        @Override
                        public boolean hasNext() {
                                return hasNext;
                        }
                        @Override
                        public int nextInt() {
                                if(hasNext) {
                                        hasNext = false;
                                        return value;
                                } else  {
                                        throw new NoSuchElementException();
                                }
                        }
                };
        }
        @Override
        public int hashCode() {
                return value;
        }
        @Override
        public String toString() {
                return String.format("[%d,%1$d]", value);
        }
        @Override
        public boolean equals(Object obj) {
                if(obj == this) {
                        return true;
                } else if(obj instanceof SingletonRange) {
                        return value == ((SingletonRange)obj).value;
                } else  {
                        return false;
                }
        }
}

class ForwardRange implements Range {
        private final int start, end;
        private final int hashCode;
        public ForwardRange(int start, int end) {
                if(start > end) {
                        throw new IllegalArgumentException("start cannot be greater than end");
                }
                this.start = start;
                this.end = end;
                this.hashCode = Arrays.hashCode(new int[] {start, end});
        }
        @Override
        public PrimitiveIterator.OfInt iterator() {
                return new PrimitiveIterator.OfInt() {
                        private int index = start;
                        @Override
                        public boolean hasNext() {
                                return index < end;
                        }
                        @Override
                        public int nextInt() {
                                if(index >= end) {
                                        throw new NoSuchElementException();
                                }
                                return index++;
                        }
                };
        }
        @Override
        public boolean contains(int x) {
                return x >= start && x < end;
        }
        @Override
        public int hashCode() {
                return hashCode;
        }
        @Override
        public String toString() {
                return String.format("[%d,%d)", start, end);
        }
        @Override
        public boolean equals(Object obj) {
                if(obj == this) {
                        return true;
                } else if(obj instanceof ForwardRange) {
                        var range = (ForwardRange)obj;
                        return start == range.start && end == range.end;
                } else  {
                        return false;
                }
        }
}

class BackwardRange implements Range {
        private final int start, end;
        private final int hashCode;
        public ForwardRange(int start, int end) {
                if(start < end) {
                        throw new IllegalArgumentException("start cannot be greater than end");
                }
                this.start = start;
                this.end = end;
                this.hashCode = Arrays.hashCode(new int[] {start, end});
        }
        @Override
        public PrimitiveIterator.OfInt iterator() {
                return new PrimitiveIterator.OfInt() {
                        private int index = start;
                        @Override
                        public boolean hasNext() {
                                return index > end;
                        }
                        @Override
                        public int nextInt() {
                                if(index <= end) {
                                        throw new NoSuchElementException();
                                }
                                return index--;
                        }
                };
        }
        @Override
        public boolean contains(int x) {
                return x >= start && x < end;
        }
        @Override
        public int hashCode() {
                return hashCode;
        }
        @Override
        public String toString() {
                return String.format("[%d,%d)", start, end);
        }
        @Override
        public boolean equals(Object obj) {
                if(obj == this) {
                        return true;
                } else if(obj instanceof BackwardRange) {
                        var range = (BackwardRange)obj;
                        return start == range.start && end == range.end;
                } else  {
                        return false;
                }
        }
}

class EmptyRange implements Range {
        public static final EmptyRange INSTANCE = new EmptyRange();
        private EmptyRange() {}
        @Override
        public boolean contains(int x) {
                return false;
        }
        @Override
        public PrimitiveIterator.OfInt iterator() {
                return new PrimitiveIterator.OfInt() {
                        @Override
                        public boolean hasNext() {
                                return false;
                        }
                        @Override
                        public int nextInt() {
                                throw new NoSuchElementException();
                        }
                };
        }
        @Override
        public int hashCode() {
                return 1;
        }
        @Override
        public boolean equals(Object obj) {
                return this == obj || obj instanceof EmptyRange;
        }
        @Override
        public String toString() {
                return "()";
        }
}
//#endregion Range

enum Day implements Named {
	MONDAY("Mon."),
	TUESDAY("Tues."),
	WEDNESDAY("Wed."),
	THURSDAY("Thurs."),
	FRIDAY("Fri."),
	SATURDAY("Sat."),
	SUNDAY("Sun.");

	public static final Set<Day> VALUES, WEEKDAYS, WEEKENDS;

	static {
		VALUES = Collections.unmodifiableSet(EnumSet.allOf(Day.class));
		WEEKDAYS = VALUES.stream().filter(day -> switch(day) {
													 case SATURDAY, SUNDAY -> false;
													 default -> true;
												 }).collect(Collectors.toSet());
		WEEKENDS = Collections.unmodifiableSet(EnumSet.complementOf(WEEKDAYS));
	}

	public final String abbreviation;

	Day(String abbr) {
		abbreviation = abbr;
	}

	@Override
	public String toString() {
		var sb = new StringBuilder();
		sb.append(name().charAt(0));
		sb.append(name(), 1, name().length());
		return sb.toString();
	}
	
	@Override
	public String getName() { return name(); }

	public static Day fromAbbreviation(String abbr) {
		return (
			switch(abbr) {
				case "Mon.", "Mon" -> MONDAY;
				case "Tues.", "Tues" -> TUESDAY;
				case "Wed.", "Wed" -> WEDNESDAY;
				case "Thurs.", "Thurs" -> THURSDAY;
				case "Fri.", "Fri" -> FRIDAY;
				case "Sat.", "Sat" -> SATURDAY;
				case "Sun.", "Sun" -> SUNDAY;
				default -> throw new IllegalArgumentException("'" + abbr + "' does not correspond to any known abbreviation.");
			}
		);
	}

}

//#region Pets
interface Animal {
	String getNoise();
	String getAnimalName();
	default void speak() {
		System.out.println(getNoise());
	}
}

abstract class AbstractAnimal implements Animal {
	protected String noise;
	private String animalName = null;
	
	protected AbstractAnimal(String noise) {
		this.noise = noise.toString(); // null-safety
	}
		
	@Override
	public String getNoise() {
		return this.noise;
	}
		
	@Override
	public String getAnimalName() {
		if(animalName == null) {
			Class<?> type = this.getClass();
			while(type.isAnonymousClass()) {
				type = type.getSuperclass();
			}
			return animalName = type.getSimpleName();
		} else {
			return animalName;
		}
	}
			
	@Override
	public int hashCode() {
		return Objects.hash(getNoise(), getAnimalName());
	}
			
	@Override
	public boolean equals(Object obj) {
		if(obj == this) {
			return true;
		} else if(obj instanceof Animal) {
			var animal = (Animal)obj;
			return Objects.equals(getNoise(), animal.getNoise())
				   && Objects.equals(getAnimalName(), animal.getAnimalName());
		} else {
			return false;
		}
	}
			
	@Override
	public String toString() {
		return String.format("%s@%08x", getAnimalName(), System.identityHashCode(this));
	}
}
	
class Dog extends AbstractAnimal {
	public Dog() {
		super("Woof!");
	}
}
		
class Cat extends AbstractAnimal {
	public Cat() {
		super("Meow");
	}
}

class Pet implements Animal, Named {
	protected final Animal animal;
	protected String name;
	
	public Pet(Animal animal, String name) {
		this.animal = Objects.requireNonNull(animal);
		this.name = name.toString();
	}
		
	@Override
	public void speak() {
		animal.speak();
	}
		
	@Override
	public String getNoise() {
		return animal.getNoise();
	}
	
	@Override
	public String getAnimalName() {
		return animal.getAnimalName();
	}
	
	@Override
	public String getName() {
		return name;
	}
		
	@Override
	public int hashCode() {
		return Objects.hash(animal.getNoise(), animal.getAnimalName(), getName());
	}
		
	@Override
	public boolean equals(Object obj) {
		if(obj == this) {
			return true;
		} else if(obj instanceof Pet) {
			var pet = (Pet)obj;
			return animal.equals(pet.animal) && Objects.equals(getName(), animal.getName());
		} else {
			return false;
		}
	}
			
	@Override
	public String toString() {
		return String.format("Pet %s \"%s\"@%08x", animal.getAnimalName(), getName(), System.identityHashCode(this));
	}
}
//#endregion Pets

//#region People
final class Address {
	private Optional<String> country, state, city, road;
	private OptionalInt zipCode, POBox;
	private Optional<Either<Integer,String>> house, floor, apartment, suite, room;
	private int hashCode = 0;
	
	private Address() {
		country = state = city = road = Optional.empty();
		zipCode = floor = POBox = OptionalInt.empty();
		house = apartment = suite = room = Optional.empty();
	}
	
	private Address(Address copy) {
		country = copy.country;
		state = copy.state;
		road = copy.road;
		house = copy.house;
		apartment = copy.apartment;
		zipCode = copy.zipCode;
		suite = copy.suite;
		floor = copy.floor;
		room = copy.room;
		POBox = copy.POBox;
		recalcHashCode();
	}
	
	//#region wither methods
	public Address withCountry(String country) {
		var addr = new Address(this);
		addr.country = opt(country);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withState(String state) {
		var addr = new Address(this);
		addr.state = opt(state);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withRoad(String road) {
		var addr = new Address(this);
		addr.road = opt(road);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withHouse(int house) {
		var addr = new Address(this);
		addr.house = optEither(house);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withHouse(String house) {
		var addr = new Address(this);
		addr.house = optEither(house);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withZipCode(int zipCode) {
		var addr = new Address(this);
		addr.zipCode = opt(zipCode);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withFloor(int floor) {
		var addr = new Address(this);
		addr.floor = optEither(floor);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withFloor(String floor) {
		var addr = new Address(this);
		addr.floor = optEither(floor);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withPOBox(int POBox) {
		var addr = new Address(this);
		addr.POBox = opt(POBox);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withApartment(int apartment) {
		var addr = new Address(this);
		addr.apartment = optEither(apartment);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withApartment(String apartment) {
		var addr = new Address(this);
		addr.apartment = optEither(apartment);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withSuite(int suite) {
		var addr = new Address(this);
		addr.suite = optEither(suite);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withSuite(String suite) {
		var addr = new Address(this);
		addr.suite = optEither(suite);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withRoom(int room) {
		var addr = new Address(this);
		addr.room = optEither(room);
		addr.recalcHashCode();
		return addr;
	}
		
	public Address withRoom(String room) {
		var addr = new Address(this);
		addr.room = optEither(room);
		addr.recalcHashCode();
		return addr;
	}
	//#endregion wither methods
		
	public int hashCode() {
		return hashCode;
	}
		
	private void recalcHashCode() {
		hashCode = Objects.hash(country, state, city, road, house, zipCode, floor, POBox, apartment, suite, room);
	}
		
	public String toString() {
		var sb = new StringBuilder();
		if(house.isPresent() && road.isPresent()) {
			sb.append(house.get().get()).append(" ").append(road.get());
		} else if(road.isPresent()) {
			sb.append(road.get());
		}
		if(city.isPresent()) {
			sep(sb, ", ");
			sb.append(city.get());
		}
		if(state.isPresent()) {
			sep(sb, ", ");
			sb.append(state.get());
		}
		if(country.isPresent()) {
			sep(sb, ", ");
			sb.append(country.get());
		}
		if(zipCode.isPresent()) {
			sep(sb, " ");
			sb.append(String.format("%05d", zipCode.get()));
		}
		if(apartment.isPresent() || suite.isPresent() || floor.isPresent() || room.isPresent()) {
			sep(sb, "\n");
			if(floor.isPresent()) {
				sb.append("Floor ").append(floor.get().get());
			}
			if(apartment.isPresent()) {
				sep(sb, ", ");
				caps(sb, 'A');
				sb.append("partment ").append(apartment.get().get());
			}
			if(suite.isPresent()) {
				sep(sb, ", ");
				caps(sb, 'S');
				sb.append("uite ").append(suite.get().get());
			}
			if(room.isPresent()) {
				sep(sb, ", ");
				caps(sb, 'R');
				sb.append("oom ").append(room.get().get());
			}
		}
		return sb.toString();
	}
		
	public Address.Builder toBuilder() {
		return new Address.Builder(this);
	}
	
	public static Address.Builder builder() {
		return new Address.Builder();
	}
	
	public static final class Builder {
		private Optional<String> country, state, city, road;
		private OptionalInt zipCode, POBox;
		private Optional<Either<Integer,String>> house, floor, apartment, suite, room;
			
		private Builder(Address copy) {
			country = copy.country;
			state = copy.state;
			road = copy.road;
			house = copy.house;
			apartment = copy.apartment;
			zipCode = copy.zipCode;
			suite = copy.suite;
			floor = copy.floor;
			room = copy.room;
			POBox = copy.POBox;
		}
		
		public Builder country(String country) {
			this.country = opt(country);
			return this;
		}
			
		public Builder state(String state) {
			this.state = opt(state);
			return this;
		}
			
		public Builder city(String city) {
			this.city = opt(city);
			return this;
		}
			
		public Builder road(String road) {
			this.road = opt(road);
			return this;
		}
			
		public Builder house(int house) {
			this.house = optEither(house);
			return this;
		}
			
		public Builder house(String house) {
			this.house = optEither(house);
			return this;
		}
			
		public Builder apartment(int apartment) {
			this.apartment = optEither(apartment);
			return this;
		}
			
		public Builder apartment(String apartment) {
			this.apartment = optEither(apartment);
			return this;
		}
			
		public Builder zipCode(int zipCode) {
			this.zipCode = opt(zipCode);
			return this;
		}
			
		public Builder suite(int suite) {
			this.suite = optEither(suite);
			return this;
		}
			
		public Builder suite(String suite) {
			this.suite = optEither(suite);
			return this;
		}
			
		public Builder floor(int floor) {
			this.floor = optEither(floor);
			return this;
		}
			
		public Builder floor(String floor) {
			this.floor = optEither(floor);
			return this;
		}
			
		public Builder room(int room) {
			this.room = optEither(room);
			return this;
		}
			
		public Builder room(String room) {
			this.room = optEither(room);
			return this;
		}
			
		public Builder POBox(int POBox) {
			this.POBox = opt(POBox);
			return this;
		}
			
		public Address build() {
			var addr = new Address();
			addr.country = country;
			addr.state = state;
			addr.road = road;
			addr.house = house;
			addr.apartment = apartment;
			addr.zipCode = zipCode;
			addr.suite = suite;
			addr.floor = floor;
			addr.room = room;
			addr.POBox = POBox;
			addr.recalcHashCode();
			return addr;
		}
	}
	
	//#region utility functions
	private static void sep(StringBuilder sb, String sep) {
		if(sb.length() != 0 && sb.charAt(sb.length()-1) != '\n') {
			sb.append(sep);
		}
	}
			
	private static void caps(StringBuilder sb, char c) {
		if(sb.length() == 0 || sb.charAt(sb.length()-1) == '\n') {
			sb.append(Character.toUpperCase(c));
		} else {
			sb.append(Character.toLowerCase(c));
		}
	}
			
	private static Optional<String> opt(String str) {
		return s == null || s.isBlank()? Optional.empty() : Optional.of(str.strip());
	}
		
	private static OptionalInt opt(int i) {
		return i < 0? OptionalInt.empty() : OptionalInt.of(i);
	}
		
	private static Optional<Either<Integer,String>> optEither(int i) {
		return i < 0? Optional.empty() : Optional.of(Either.first(i));
	}
		
	private static Optional<Either<Integer,String>> optEither(String str) {
		return s == null || s.isBlank()? Optional.empty() : Optional.of(Either.second(str.strip()));
	}
	//#endregion utility functions	
}

interface User extends Named {
	Collection<Pet> getPets();
	Optional<Address> getAddress();
	void setAddress(Address addr);
	void setHomeless();
	int getAge();
	boolean hasAge();
	void setAge(int newAge);
	default boolean isHomeless() {
		return getAddress().isEmpty();
	}
	void setName(String newName);
}

class Person implements User {
	private final Set<Pet> pets = Collections.newSetFromMap(new IdentityHashMap<Pet,Boolean>());
	private Optional<Address> address = Optional.empty();
	private int age = -1;
	private String name;
	
	public Person(String name) {
		this.setName(name);
	}
		
	@Override
	public String getName() {
		return name;
	}
		
	@Override
	public void setName(String newName) {
		Objects.requireNonNull(newName);
		if(newName.isBlank()) {
			throw new IllegalArgumentException("Name may not be blank");
		}
		this.name = newName.strip();
	}
		
	@Override
	public Set<Pet> getPets() {
		return pets;
	}
		
	@Override
	public Optional<Address> getAddress() {
		return address;
	}
		
	@Override
	public void setAddress(Address newAddress) {
		this.address = Objects.requireNonNull(newAddress);
	}
		
	@Override
	public void setHomeless() {
		this.address = Optional.empty();
	}
		
	@Override
	public int getAge() {
		return age;
	}
	
	@Override
	public boolean hasAge() {
		return age != -1;
	}
		
	@Override
	public void setAge(int newAge) {
		if(newAge < -1) {
			throw new IllegalArgumentException();
		}
		this.age = newAge;
	}
		
	@Override
	public String toString() {
		if(hasAge()) {
			return String.format("%s, age %d - %s; pets: %s", getName(), getAge(), isHomeless()? "homeless" : getAddress().get().toString().replace("\n", " / "), getPets());
		} else {
			return String.format("%s - %s; pets: %s", getName(), isHomeless()? "homeless" : getAddress().get().toString().replace("\n", " / "), getPets());
		}
	}
		
	@Override
	public int hashCode() {
		return Objects.hash(getName(), getAge(), getAddress());
	}
		
	@Override
	public boolean equals(Object obj) {
		if(obj == this) {
			return true;
		} else if(obj instanceof User) {
			var user = (User)obj;
			return (user.getPets().size() == getPets().size() && user.getPets().containsAll(getPets())
					&& getName().equals(user.getName())
					&& getAddress().equals(user.getAddress())
					&& getAge() == user.getAge());
		} else {
			return false;
		}
	}
}
//#endregion People
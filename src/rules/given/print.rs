use super::{
	CourseRule, Given, GivenAreasWhatOptions, GivenAttendancesWhatOptions, GivenCoursesWhatOptions,
	GivenPerformancesWhatOptions, RepeatMode, Rule,
};
use crate::action;
use crate::rules::req_ref;
use crate::traits::print;
use crate::traits::print::Print;
use crate::util::Oxford;

impl print::Print for Rule {
	fn print(&self) -> print::Result {
		use std::fmt::Write;

		let mut output = String::new();

		let rule = match &self.given {
			Given::AllCourses { what } => self.print_given_all_courses(what)?,
			Given::TheseCourses {
				what,
				courses,
				repeats: mode,
			} => self.print_given_these_courses(courses, mode, what)?,
			Given::TheseRequirements { what, requirements } => {
				self.print_given_these_requirements(requirements, what)?
			}
			Given::Areas { what } => self.print_given_areas(what)?,
			Given::NamedVariable { save, what } => self.print_given_save(save, what)?,
			Given::Performances { what } => self.print_given_performances(what)?,
			Given::Attendances { what } => self.print_given_attendances(what)?,
		};

		write!(&mut output, "{}", rule)?;

		Ok(output)
	}
}

impl Rule {
	fn print_filter(&self) -> print::Result {
		match &self.filter {
			Some(f) => Ok(format!(" taken {}", f.print()?)),
			None => Ok("".to_string()),
		}
	}

	fn print_given_all_courses(&self, what: &GivenCoursesWhatOptions) -> print::Result {
		use std::fmt::Write;
		use GivenCoursesWhatOptions as What;

		let mut output = String::new();
		let action = self.action.print()?;
		let filter = self.print_filter()?;

		match &what {
			What::Courses => {
				let plur = self.action.should_pluralize();
				let word = if plur { "courses" } else { "course" };

				write!(&mut output, "have {} {}{}", action, word, filter)?;
			}
			What::DistinctCourses => {
				let plur = self.action.should_pluralize();
				let word = if plur { "distinct courses" } else { "course" };

				write!(&mut output, "have {} {}{}", action, word, filter)?;
			}
			What::Credits => {
				let plur = self.action.should_pluralize();
				let word = if plur { "credits" } else { "credit" };

				write!(
					&mut output,
					"have enough courses{} to obtain {} {}",
					filter, action, word
				)?;
			}
			What::Departments => {
				let plur = self.action.should_pluralize();
				let word = if plur { "departments" } else { "department" };

				write!(&mut output, "have enough courses{} to span {} {}", filter, action, word)?;
			}
			What::Grades => {
				let plur = self.action.should_pluralize();
				let word = if plur { "courses" } else { "course" };

				write!(
					&mut output,
					"maintain an average GPA {} from {}{}",
					action, word, filter
				)?;
			}
			What::Terms => {
				let plur = self.action.should_pluralize();
				let word = if plur { "terms" } else { "term" };

				write!(&mut output, "have enough courses{} to span {} {}", filter, action, word)?;
			}
		}

		Ok(output)
	}

	fn print_given_areas(&self, what: &GivenAreasWhatOptions) -> print::Result {
		use std::fmt::Write;
		use GivenAreasWhatOptions as What;

		let mut output = String::new();
		let filter = match &self.filter {
			Some(f) => format!(" {}", f.print()?),
			None => "".to_string(),
		};

		match &what {
			What::Areas => {
				// TODO: find a better way to special-case "exactly one" major
				let action = self.action.print()?;
				let action = action.replace("exactly ", "");
				write!(&mut output, "declare {}{}", action, filter)?;
			}
		}

		Ok(output)
	}

	fn print_given_performances(&self, what: &GivenPerformancesWhatOptions) -> print::Result {
		use std::fmt::Write;
		use GivenPerformancesWhatOptions as What;

		let mut output = String::new();
		let filter = match &self.filter {
			Some(f) => format!(" {}", f.print()?),
			None => "".to_string(),
		};

		match &what {
			What::Performances => {
				let action = self.action.print()?;
				write!(&mut output, "perform {} recitals{}", action, filter)?;
			}
		}

		Ok(output)
	}

	fn print_given_attendances(&self, what: &GivenAttendancesWhatOptions) -> print::Result {
		use std::fmt::Write;
		use GivenAttendancesWhatOptions as What;

		let mut output = String::new();
		let filter = match &self.filter {
			Some(f) => format!(" {}", f.print()?),
			None => "".to_string(),
		};

		match &what {
			What::Attendances => {
				let action = self.action.print()?;
				write!(&mut output, "attend {}{} recitals", action, filter)?;
			}
		}

		Ok(output)
	}

	fn print_given_these_courses(
		&self,
		courses: &[CourseRule],
		mode: &RepeatMode,
		what: &GivenCoursesWhatOptions,
	) -> print::Result {
		use std::fmt::Write;
		use GivenCoursesWhatOptions as What;

		let mut output = String::new();
		let filter = match &self.filter {
			Some(f) => Some(format!(" {}", f.print()?)),
			None => None,
		};

		let courses: Vec<String> = courses.iter().map(|r| r.print().unwrap()).collect();

		match (mode, what) {
			(RepeatMode::First, What::Courses) | (RepeatMode::Last, What::Courses) => {
				match courses.len() {
					1 => {
						// TODO: expose last vs. first in output somehow?
						write!(&mut output, "take {}", courses.oxford("and"))?;
					}
					2 => match (&self.action.lhs, &self.action.op, &self.action.rhs) {
						(
							action::Command::Count,
							Some(action::Operator::GreaterThanEqualTo),
							Some(action::Value::Integer(n)),
						) => match n {
							1 => {
								write!(&mut output, "take either {} or {}", courses[0], courses[1])?;
							}
							2 => {
								write!(&mut output, "take both {} and {}", courses[0], courses[1])?;
							}
							_ => panic!("should not require <1 or >len of the number of courses given"),
						},
						_ => unimplemented!("most actions on two-up given:these-courses rules"),
					},
					3...5 => {
						// TODO: expose last vs. first in output somehow?
						let plur = self.action.should_pluralize();
						let word = if plur { "courses" } else { "course" };
						write!(
							&mut output,
							"take {} {} from among {}",
							self.action.print()?,
							word,
							courses.oxford("and")
						)?;
					}
					_ => {
						// TODO: expose last vs. first in output somehow?
						let plur = self.action.should_pluralize();
						let word = if plur { "courses" } else { "course" };

						let as_list: Vec<_> = courses.iter().map(|l| format!("- {}", l)).collect();

						write!(
							&mut output,
							"take {} {} from among the following:\n\n{}",
							self.action.print()?,
							word,
							as_list.join("\n")
						)?;
					}
				}
			}
			(RepeatMode::All, What::Courses) => {
				// TODO: special-case "once" and "twice"
				let plur = self.action.should_pluralize();
				let word = if plur { "times" } else { "time" };

				match (&self.action.lhs, &self.action.op, &self.action.rhs) {
					(
						action::Command::Count,
						Some(action::Operator::GreaterThanEqualTo),
						Some(action::Value::Integer(1)),
					) => match courses.len() {
						1...5 => {
							write!(
								&mut output,
								"take {} {} {}",
								courses.oxford("or"),
								self.action.print()?,
								word
							)?;
						}
						_ => {
							let as_list: Vec<_> = courses.iter().map(|l| format!("- {}", l)).collect();

							write!(
								&mut output,
								"take {} of the following courses:\n\n{}",
								self.action.print()?,
								as_list.join("\n")
							)?;
						}
					},
					_ => match courses.len() {
						1 => {
							write!(
								&mut output,
								"take {} {} {}",
								courses.oxford("and"),
								self.action.print()?,
								word
							)?;
						}
						_ => {
							write!(
								&mut output,
								"take a combination of {} {} {}",
								courses.oxford("and"),
								self.action.print()?,
								word
							)?;
						}
					},
				}
			}
			(RepeatMode::All, What::Credits) => {
				// TODO: special-case "once" and "twice"
				let plur = self.action.should_pluralize();
				let word = if plur { "credits" } else { "credit" };

				write!(
					&mut output,
					"take {} enough times to yield {} {}",
					courses.oxford("and"),
					self.action.print()?,
					word
				)?;
			}
			(RepeatMode::All, What::Terms) => {
				// TODO: special-case "once" and "twice"
				let plur = self.action.should_pluralize();
				let word = if plur { "terms" } else { "term" };

				write!(
					&mut output,
					"take {} enough times to span {} {}",
					courses.oxford("and"),
					self.action.print()?,
					word
				)?;
			}
			_ => unimplemented!("certain modes of given:these-courses"),
		}

		if let Some(f) = filter {
			write!(&mut output, "{}", f)?;
		}

		Ok(output)
	}

	fn print_given_these_requirements(
		&self,
		requirements: &[req_ref::Rule],
		what: &GivenCoursesWhatOptions,
	) -> print::Result {
		use std::fmt::Write;
		use GivenCoursesWhatOptions as What;

		let mut output = String::new();

		let requirements: Vec<String> = requirements
			.iter()
			.filter_map(|r| match r.print() {
				Ok(p) => Some(p),
				Err(_) => None,
			})
			.collect();

		writeln!(&mut output, "have the following be true:\n")?;
		let mut index = 0;

		index += 1;
		match requirements.len() {
			0 => panic!("no requirements given!"),
			1 | 2 | 3 => {
				let singular = requirements.len() == 1;
				let word = if singular { "requirement" } else { "requirements" };
				writeln!(
					&mut output,
					"{index}. given the results of the {list} {word},",
					index = index,
					list = requirements.oxford("and"),
					word = word
				)?;
			}
			_ => {
				writeln!(
					&mut output,
					"{index}. given the results of the following requirements",
					index = index
				)?;
				for req in requirements {
					writeln!(&mut output, "    - {}", req)?;
				}
			}
		};

		match &self.filter {
			Some(f) => {
				index += 1;
				writeln!(
					&mut output,
					"{index}. restricted to only courses taken {filter},",
					index = index,
					filter = f.print()?
				)?;
			}
			None => (),
		};

		index += 1;
		let pluralize = self.action.should_pluralize();

		match &what {
			What::Courses => {
				let word = if pluralize { "courses" } else { "course" };

				writeln!(
					&mut output,
					"{index}. there must be {action} {word}",
					index = index,
					action = self.action.print()?,
					word = word,
				)?;
			}
			What::DistinctCourses => {
				let word = if pluralize {
					"distinct courses"
				} else {
					"distinct course"
				};

				writeln!(
					&mut output,
					"{index}. there must be {action} {word}",
					index = index,
					action = self.action.print()?,
					word = word,
				)?;
			}
			What::Credits => {
				let word = if pluralize { "credits" } else { "credit" };

				writeln!(
					&mut output,
					"{index}. there must be {action} {word}",
					index = index,
					action = self.action.print()?,
					word = word,
				)?;
			}
			What::Departments => {
				let word = if pluralize {
					"distinct departments"
				} else {
					"department"
				};

				writeln!(
					&mut output,
					"{index}. there must be {action} {word}",
					index = index,
					action = self.action.print()?,
					word = word,
				)?;
			}
			What::Grades => {
				writeln!(
					&mut output,
					"{index}. there must be an average GPA {action}",
					index = index,
					action = self.action.print()?,
				)?;
			}
			What::Terms => {
				let word = if pluralize { "terms" } else { "term" };

				writeln!(
					&mut output,
					"{index}. there must be courses in {action} {word}",
					index = index,
					action = self.action.print()?,
					word = word,
				)?;
			}
		};

		Ok(output)
	}

	fn print_given_save(&self, save: &str, what: &GivenCoursesWhatOptions) -> print::Result {
		use std::fmt::Write;
		use GivenCoursesWhatOptions as What;

		let mut output = String::new();
		let filter = self.print_filter()?;

		match &what {
			What::Courses => {
				let plur = self.action.should_pluralize();
				let word = if plur { "courses" } else { "course" };

				write!(&mut output, "in the subset “{}”, ", save)?;
				write!(&mut output, "there must be {} {}{}", self.action.print()?, word, filter)?;
				// write!(&mut output, " in the subset “{}”", save)?;
			}
			What::DistinctCourses => {
				let plur = self.action.should_pluralize();
				let word = if plur { "distinct courses" } else { "course" };

				write!(&mut output, "in the subset “{}”, ", save)?;
				write!(&mut output, "there must be {} {}{}", self.action.print()?, word, filter)?;
				// write!(&mut output, " in the subset “{}”", save)?;
			}
			What::Credits => {
				let plur = self.action.should_pluralize();
				let word = if plur { "credits" } else { "credit" };

				write!(&mut output, "in the subset “{}”, ", save)?;
				write!(
					&mut output,
					"there must be enough courses{} to obtain {} {}",
					filter,
					self.action.print()?,
					word
				)?;
			}
			What::Departments => {
				let plur = self.action.should_pluralize();
				let word = if plur { "departments" } else { "department" };

				write!(&mut output, "in the subset “{}”, ", save)?;
				write!(
					&mut output,
					"there must be enough courses{} to span {} {}",
					filter,
					self.action.print()?,
					word
				)?;
			}
			What::Grades => {
				let plur = self.action.should_pluralize();
				let word = if plur { "courses" } else { "course" };

				write!(&mut output, "courses from the subset “{}” ", save)?;
				write!(
					&mut output,
					"must maintain an average GPA {} from {}{}",
					self.action.print()?,
					word,
					filter
				)?;
			}
			What::Terms => {
				let plur = self.action.should_pluralize();
				let word = if plur { "terms" } else { "term" };

				write!(&mut output, "in the subset “{}”, ", save)?;
				write!(
					&mut output,
					"there must be enough courses{} to span {} {}",
					filter,
					self.action.print()?,
					word
				)?;
			}
		}

		Ok(output)
	}
}

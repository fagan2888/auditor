use crate::rules::{course, req_ref};
use crate::traits::{print, Util};
use crate::util::{self, Oxford};
use crate::{action, filter, limit};

#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
pub struct Rule {
	#[serde(flatten)]
	pub given: Given,
	#[serde(default)]
	pub limit: Option<Vec<limit::Limiter>>,
	#[serde(rename = "where", default, deserialize_with = "filter::deserialize_with")]
	pub filter: Option<filter::Clause>,
	pub what: What,
	#[serde(rename = "do", deserialize_with = "util::string_or_struct_parseerror")]
	pub action: action::Action,
}

impl Util for Rule {
	fn has_save_rule(&self) -> bool {
		match &self.given {
			Given::NamedVariable { .. } => true,
			_ => false,
		}
	}
}

impl print::Print for Rule {
	fn print(&self) -> print::Result {
		use std::fmt::Write;

		let mut output = String::new();

		let filter = match &self.filter {
			Some(f) => format!(" {}", f.print()?),
			None => "".to_string(),
		};

		match &self.given {
			Given::AllCourses => match &self.what {
				What::Courses => {
					let plur = self.action.should_pluralize();
					let word = if plur { "courses" } else { "course" };

					write!(&mut output, "take {} {}{}", self.action.print()?, word, filter)?;
				}
				What::DistinctCourses => {
					let plur = self.action.should_pluralize();
					let word = if plur { "distinct courses" } else { "course" };

					write!(&mut output, "take {} {}{}", self.action.print()?, word, filter)?;
				}
				What::Credits => {
					let plur = self.action.should_pluralize();
					let word = if plur { "credits" } else { "credit" };

					write!(
						&mut output,
						"take enough courses{} to obtain {} {}",
						filter,
						self.action.print()?,
						word
					)?;
				}
				What::Departments => {
					let plur = self.action.should_pluralize();
					let word = if plur { "departments" } else { "department" };

					write!(
						&mut output,
						"take enough courses{} to span {} {}",
						filter,
						self.action.print()?,
						word
					)?;
				}
				What::Grades => {
					let plur = self.action.should_pluralize();
					let word = if plur { "courses" } else { "course" };

					write!(
						&mut output,
						"maintain an average GPA {} from {}{}",
						self.action.print()?,
						word,
						filter
					)?;
				}
				What::Terms => {
					let plur = self.action.should_pluralize();
					let word = if plur { "terms" } else { "term" };

					write!(
						&mut output,
						"take enough courses{} to span {} {}",
						filter,
						self.action.print()?,
						word
					)?;
				}
				What::AreasOfStudy => panic!("given:all-courses and what:area makes no sense"),
			},
			Given::TheseCourses { courses, repeats: mode } => {
				let courses_vec = courses;
				let courses = courses
					.iter()
					.map(|r| r.print().unwrap())
					.collect::<Vec<String>>()
					.oxford("and");

				match (mode, &self.what) {
					(RepeatMode::First, What::Courses) | (RepeatMode::Last, What::Courses) => {
						match courses_vec.len() {
							1 => {
								// TODO: expose last vs. first in output somehow?
								write!(&mut output, "take {}", courses)?;
							}
							2 => match (&self.action.lhs, &self.action.op, &self.action.rhs) {
								(
									action::Value::Command(action::Command::Count),
									Some(action::Operator::GreaterThanEqualTo),
									Some(action::Value::Integer(n)),
								) => match n {
									1 => {
										write!(
											&mut output,
											"take either {} or {}",
											courses_vec[0].print()?,
											courses_vec[1].print()?
										)?;
									}
									2 => {
										write!(
											&mut output,
											"take both {} and {}",
											courses_vec[0].print()?,
											courses_vec[1].print()?
										)?;
									}
									_ => panic!("should not require <1 or >len of the number of courses given"),
								},
								_ => unimplemented!("most actions on two-up given:these-courses rules"),
							},
							_ => {
								// TODO: expose last vs. first in output somehow?
								let plur = self.action.should_pluralize();
								let word = if plur { "courses" } else { "course" };
								write!(
									&mut output,
									"take {} {} from among {}",
									self.action.print()?,
									word,
									courses
								)?;
							}
						}
					}
					(RepeatMode::All, What::Courses) => {
						// TODO: special-case "once" and "twice"
						let plur = self.action.should_pluralize();
						let word = if plur { "times" } else { "time" };

						write!(&mut output, "take {} {} {}", courses, self.action.print()?, word)?;
					}
					(RepeatMode::All, What::Credits) => {
						// TODO: special-case "once" and "twice"
						let plur = self.action.should_pluralize();
						let word = if plur { "credits" } else { "credit" };

						write!(
							&mut output,
							"take {} enough times to yield {} {}",
							courses,
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
							courses,
							self.action.print()?,
							word
						)?;
					}
					_ => unimplemented!("certain modes of given:these-courses"),
				}
			}
			Given::TheseRequirements { requirements } => {
				match &self.what {
					What::Courses => {
						write!(&mut output, "take enough courses{} {}", filter, self.action.print()?)?;
					}
					What::DistinctCourses => {
						write!(&mut output, "take enough courses{} {}", self.action.print()?, filter)?;
					}
					What::Credits => {
						let plur = self.action.should_pluralize();
						let word = if plur { "credits" } else { "credit" };

						write!(
							&mut output,
							"take enough courses{} to obtain {} {}",
							filter,
							self.action.print()?,
							word
						)?;
					}
					What::Departments => {
						let plur = self.action.should_pluralize();
						let word = if plur { "departments" } else { "department" };

						write!(
							&mut output,
							"take enough courses{} to span {} {}",
							filter,
							self.action.print()?,
							word
						)?;
					}
					What::Grades => {
						let plur = self.action.should_pluralize();
						let word = if plur { "courses" } else { "course" };

						write!(
							&mut output,
							"maintain an average GPA {} from {}{}",
							self.action.print()?,
							word,
							filter
						)?;
					}
					What::Terms => {
						let plur = self.action.should_pluralize();
						let word = if plur { "terms" } else { "term" };

						write!(
							&mut output,
							"take enough courses{} to span {} {}",
							filter,
							self.action.print()?,
							word
						)?;
					}
					What::AreasOfStudy => unimplemented!("given:these-requirements, what:areas makes no sense"),
				}

				let requirements: Vec<String> = requirements
					.into_iter()
					.filter_map(|r| match r.print() {
						Ok(p) => Some(p),
						Err(_) => None,
					})
					.collect();

				write!(
					&mut output,
					" from among courses matched by the {} requirements",
					requirements.oxford("and")
				)?;
			}
			Given::AreasOfStudy => match self.what {
				What::AreasOfStudy => {
					// TODO: find a better way to special-case "exactly one" major
					let action = self.action.print()?;
					let action = action.replace("exactly ", "");
					write!(&mut output, "declare {}{}", action, filter)?;
				}
				_ => panic!("given: areas, what: !areas…"),
			},
			Given::NamedVariable { save } => match &self.what {
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
				What::AreasOfStudy => unimplemented!("given:variable, what:areas is not yet implemented"),
			},
		}

		Ok(output)
	}
}

// impl Rule {
//     fn validate(&self) -> Result<(), util::ValidationError> {
//         match (&self.given, &self.what) {
//             (Given::AreasOfStudy, What::AreasOfStudy) => (),
//             (Given::AreasOfStudy, _) => {
//                 return Err(util::ValidationError::GivenAreasMustOutputAreas)
//             }
//             _ => (),
//         }
//
//         Ok(())
//     }
// }

#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
#[serde(tag = "given")]
pub enum Given {
	#[serde(rename = "courses")]
	AllCourses,
	#[serde(rename = "these courses")]
	TheseCourses {
		courses: Vec<CourseRule>,
		repeats: RepeatMode,
	},
	#[serde(rename = "these requirements")]
	TheseRequirements { requirements: Vec<req_ref::Rule> },
	#[serde(rename = "areas of study")]
	AreasOfStudy,
	#[serde(rename = "save")]
	NamedVariable { save: String },
}

#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
#[serde(untagged)]
pub enum CourseRule {
	Value(#[serde(deserialize_with = "util::string_or_struct")] course::Rule),
}

impl print::Print for CourseRule {
	fn print(&self) -> print::Result {
		match &self {
			CourseRule::Value(v) => v.print(),
		}
	}
}

#[derive(Debug, PartialEq, Serialize, Deserialize, Clone)]
pub enum RepeatMode {
	#[serde(rename = "first")]
	First,
	#[serde(rename = "last")]
	Last,
	#[serde(rename = "all")]
	All,
}

#[derive(Debug, Eq, PartialEq, Serialize, Deserialize, Clone)]
pub enum What {
	#[serde(rename = "courses")]
	Courses,
	#[serde(rename = "distinct courses")]
	DistinctCourses,
	#[serde(rename = "credits")]
	Credits,
	#[serde(rename = "departments")]
	Departments,
	#[serde(rename = "terms")]
	Terms,
	#[serde(rename = "grades")]
	Grades,
	#[serde(rename = "areas of study")]
	AreasOfStudy,
}

#[cfg(test)]
mod tests {
	use super::*;
	use crate::traits::print::Print;

	#[test]
	fn serialize_all_courses() {
		let data = Rule {
			given: Given::AllCourses,
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::Courses,
			action: "count > 2".parse().unwrap(),
		};

		let expected = r#"---
given: courses
limit: []
where: {}
what: courses
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual = serde_yaml::to_string(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_all_courses() {
		let expected = Rule {
			given: Given::AllCourses,
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::Courses,
			action: "count > 2".parse().unwrap(),
		};

		let data = r#"---
given: courses
limit: []
where: {}
what: courses
do: count > 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);

		let data = r#"---
given: courses
limit: []
where: {}
what: courses
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn serialize_these_courses() {
		let data = Rule {
			given: Given::TheseCourses {
				courses: vec![
					CourseRule::Value(course::Rule {
						course: "ASIAN 110".to_string(),
						..Default::default()
					}),
					CourseRule::Value(course::Rule {
						course: "ASIAN 110".to_string(),
						..Default::default()
					}),
				],
				repeats: RepeatMode::First,
			},
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::Courses,
			action: "count > 2".parse().unwrap(),
		};

		let expected = r#"---
given: these courses
courses:
  - course: ASIAN 110
  - course: ASIAN 110
repeats: first
limit: []
where: {}
what: courses
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual = serde_yaml::to_string(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_these_courses() {
		let expected = Rule {
			given: Given::TheseCourses {
				courses: vec![
					CourseRule::Value(course::Rule {
						course: "ASIAN 110".to_string(),
						..Default::default()
					}),
					CourseRule::Value(course::Rule {
						course: "ASIAN 110".to_string(),
						..Default::default()
					}),
				],
				repeats: RepeatMode::First,
			},
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::Courses,
			action: "count > 2".parse().unwrap(),
		};

		let data = r#"---
given: these courses
courses:
  - ASIAN 110
  - course: ASIAN 110
repeats: first
limit: []
where: {}
what: courses
do: count > 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);

		let data = r#"---
given: these courses
courses:
  - ASIAN 110
  - course: ASIAN 110
repeats: first
limit: []
where: {}
what: courses
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn serialize_these_requirements() {
		let data = Rule {
			given: Given::TheseRequirements {
				requirements: vec![
					req_ref::Rule {
						requirement: "A Name 1".to_string(),
						optional: false,
					},
					req_ref::Rule {
						requirement: "A Name 2".to_string(),
						optional: true,
					},
				],
			},
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::Courses,
			action: "count > 2".parse().unwrap(),
		};

		let expected = r#"---
given: these requirements
requirements:
  - requirement: A Name 1
    optional: false
  - requirement: A Name 2
    optional: true
limit: []
where: {}
what: courses
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual = serde_yaml::to_string(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_these_requirements() {
		let expected = Rule {
			given: Given::TheseRequirements {
				requirements: vec![
					req_ref::Rule {
						requirement: "A Name 1".to_string(),
						optional: false,
					},
					req_ref::Rule {
						requirement: "A Name 2".to_string(),
						optional: true,
					},
				],
			},
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::Courses,
			action: "count > 2".parse().unwrap(),
		};

		let data = r#"---
given: these requirements
requirements:
  - requirement: A Name 1
  - {requirement: A Name 2, optional: true}
limit: []
where: {}
what: courses
do: count > 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);

		let data = r#"---
given: these requirements
requirements:
  - requirement: A Name 1
  - {requirement: A Name 2, optional: true}
limit: []
where: {}
what: courses
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn serialize_areas() {
		let data = Rule {
			given: Given::AreasOfStudy,
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::AreasOfStudy,
			action: "count > 2".parse().unwrap(),
		};

		let expected = r#"---
given: areas of study
limit: []
where: {}
what: areas of study
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual = serde_yaml::to_string(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_areas() {
		let expected = Rule {
			given: Given::AreasOfStudy,
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::AreasOfStudy,
			action: "count > 2".parse().unwrap(),
		};

		let data = r#"---
given: areas of study
limit: []
where: {}
what: areas of study
do: count > 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);

		let data = r#"---
given: areas of study
limit: []
where: {}
what: areas of study
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn serialize_save() {
		let data = Rule {
			given: Given::NamedVariable {
				save: String::from("$my_var"),
			},
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::Courses,
			action: "count > 2".parse().unwrap(),
		};

		let expected = r#"---
given: save
save: $my_var
limit: []
where: {}
what: courses
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual = serde_yaml::to_string(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_save() {
		let expected = Rule {
			given: Given::NamedVariable {
				save: String::from("$my_var"),
			},
			limit: Some(vec![]),
			filter: Some(filter::Clause::new()),
			what: What::Courses,
			action: "count > 2".parse().unwrap(),
		};

		let data = r#"---
given: save
save: $my_var
limit: []
where: {}
what: courses
do: count > 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);

		let data = r#"---
given: save
save: $my_var
limit: []
where: {}
what: courses
do:
  lhs:
    Command: Count
  op: GreaterThan
  rhs:
    Integer: 2"#;

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_save_ba_interim() {
		let data = r#"---
given: save
save: $interim_courses
what: courses
do: count >= 3"#;

		let expected = Rule {
			given: Given::NamedVariable {
				save: String::from("$interim_courses"),
			},
			limit: None,
			filter: None,
			what: What::Courses,
			action: "count >= 3".parse().unwrap(),
		};

		let actual: Rule = serde_yaml::from_str(&data).unwrap();

		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_filter_gereqs_single() {
		let data = r#"{where: {gereqs: 'FYW'}, given: courses, what: courses, do: count > 1}"#;

		let expected: filter::Clause = btreemap! {
			"gereqs".into() => filter::WrappedValue::Single(filter::TaggedValue {
				op: action::Operator::EqualTo,
				value: filter::Value::String("FYW".into()),
			}),
		};
		let expected = Rule {
			given: Given::AllCourses,
			limit: None,
			filter: Some(expected),
			what: What::Courses,
			action: "count > 1".parse().unwrap(),
		};

		let actual: Rule = serde_yaml::from_str(&data).unwrap();
		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_filter_gereqs_or() {
		let data = r#"{where: {gereqs: 'MCD | MCG'}, given: courses, what: courses, do: count > 1}"#;

		let expected: filter::Clause = btreemap! {
			"gereqs".into() => filter::WrappedValue::Or(vec![
				filter::TaggedValue {
					op: action::Operator::EqualTo,
					value: filter::Value::String("MCD".into()),
				},
				filter::TaggedValue {
					op: action::Operator::EqualTo,
					value: filter::Value::String("MCG".into()),
				},
			]),
		};
		let expected = Rule {
			given: Given::AllCourses,
			limit: None,
			filter: Some(expected),
			what: What::Courses,
			action: "count > 1".parse().unwrap(),
		};

		let actual: Rule = serde_yaml::from_str(&data).unwrap();
		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_filter_level_gte() {
		let data = r#"{where: {level: '>= 200'}, given: courses, what: courses, do: count > 1}"#;

		let expected: filter::Clause = btreemap! {
			"level".into() => filter::WrappedValue::Single(filter::TaggedValue {
				op: action::Operator::GreaterThanEqualTo,
				value: filter::Value::Integer(200),
			}),
		};
		let expected = Rule {
			given: Given::AllCourses,
			limit: None,
			filter: Some(expected),
			what: What::Courses,
			action: "count > 1".parse().unwrap(),
		};

		let actual: Rule = serde_yaml::from_str(&data).unwrap();
		assert_eq!(actual, expected);
	}

	#[test]
	fn deserialize_filter_graded_bool() {
		let data = r#"{where: {graded: 'true'}, given: courses, what: courses, do: count > 1}"#;

		let expected: filter::Clause = btreemap! {
			"graded".into() => filter::WrappedValue::Single(filter::TaggedValue {
				op: action::Operator::EqualTo,
				value: filter::Value::Bool(true),
			}),
		};
		let expected = Rule {
			given: Given::AllCourses,
			limit: None,
			filter: Some(expected),
			what: What::Courses,
			action: "count > 1".parse().unwrap(),
		};

		let actual: Rule = serde_yaml::from_str(&data).unwrap();
		assert_eq!(actual, expected);
	}

	#[test]
	fn pretty_print_inline() {
		let input: Rule = serde_yaml::from_str(&"{given: courses, what: courses, do: count >= 1}").unwrap();
		let expected = "take at least one course";
		assert_eq!(expected, input.print().unwrap());
	}

	#[test]
	fn pretty_print_inline_filters() {
		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: {gereqs: FOL-C}, what: courses, do: count >= 1}").unwrap();
		let expected = "take at least one course with the “FOL-C” general education attribute";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: {gereqs: SPM}, what: distinct courses, do: count >= 2}")
				.unwrap();
		let expected = "take at least two distinct courses with the “SPM” general education attribute";
		assert_eq!(expected, input.print().unwrap());
	}

	#[test]
	fn pretty_print_inline_repeats() {
		let input: Rule = serde_yaml::from_str(
			&"{given: these courses, repeats: all, courses: [THEAT 233], what: courses, do: count >= 1}",
		)
		.unwrap();
		let expected = "take THEAT 233 at least one time";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule = serde_yaml::from_str(
			&"{given: these courses, repeats: all, courses: [THEAT 233], what: courses, do: count >= 4}",
		)
		.unwrap();
		let expected = "take THEAT 233 at least four times";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule = serde_yaml::from_str(
			&"{given: these courses, repeats: all, courses: [THEAT 233, THEAT 253], what: courses, do: count >= 4}",
		)
		.unwrap();
		let expected = "take THEAT 233 and THEAT 253 at least four times";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule = serde_yaml::from_str(
			&"{given: these courses, repeats: all, courses: [THEAT 233], what: credits, do: sum >= 4}",
		)
		.unwrap();
		let expected = "take THEAT 233 enough times to yield at least four credits";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule = serde_yaml::from_str(
			&"{given: these courses, repeats: first, courses: [THEAT 233], what: courses, do: count >= 1}",
		)
		.unwrap();
		let expected = "take THEAT 233";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule = serde_yaml::from_str(
			&"{given: these courses, repeats: first, courses: [THEAT 233, THEAT 253], what: courses, do: count >= 1}",
		)
		.unwrap();
		let expected = "take either THEAT 233 or THEAT 253";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule = serde_yaml::from_str(
			&"{given: these courses, repeats: first, courses: [THEAT 233, THEAT 253], what: courses, do: count >= 2}",
		)
		.unwrap();
		let expected = "take both THEAT 233 and THEAT 253";
		assert_eq!(expected, input.print().unwrap());
	}

	#[test]
	fn pretty_print_inline_credits() {
		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: {gereqs: FOL-C}, what: credits, do: sum >= 1}").unwrap();
		let expected =
			"take enough courses with the “FOL-C” general education attribute to obtain at least one credit";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: {semester: Interim}, what: credits, do: sum >= 3}").unwrap();
		let expected = "take enough courses during Interim semesters to obtain at least three credits";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: {semester: Fall}, what: credits, do: sum >= 10}").unwrap();
		let expected = "take enough courses during Fall semesters to obtain at least ten credits";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: {semester: Fall | Interim}, what: credits, do: sum >= 10}")
				.unwrap();
		let expected = "take enough courses during a Fall or Interim semester to obtain at least ten credits";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: {year: '2012'}, what: credits, do: sum >= 3}").unwrap();
		let expected = "take enough courses during the 2012-13 academic year to obtain at least three credits";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule = serde_yaml::from_str(
			&"{given: courses, where: {institution: St. Olaf College}, what: credits, do: sum >= 17}",
		)
		.unwrap();
		let expected = "take enough courses at St. Olaf College to obtain at least 17 credits";
		assert_eq!(expected, input.print().unwrap());
	}

	#[test]
	fn pretty_print_inline_departments() {
		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: {gereqs: FOL-C}, what: departments, do: count >= 2}")
				.unwrap();
		let expected =
			"take enough courses with the “FOL-C” general education attribute to span at least two departments";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: {semester: Interim}, what: departments, do: count >= 1}")
				.unwrap();
		let expected = "take enough courses during Interim semesters to span at least one department";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule = serde_yaml::from_str(
			&"{given: courses, where: { department: '! MATH' }, what: departments, do: count >= 2}",
		)
		.unwrap();
		let expected = "take enough courses outside of the MATH department to span at least two departments";
		assert_eq!(expected, input.print().unwrap());
	}

	#[test]
	fn pretty_print_inline_grades() {
		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: { gereqs: FOL-C }, what: grades, do: average >= 2.0}")
				.unwrap();
		let expected =
			"maintain an average GPA at or above 2.00 from courses with the “FOL-C” general education attribute";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: { semester: Interim }, what: grades, do: average >= 3.0}")
				.unwrap();
		let expected = "maintain an average GPA at or above 3.00 from courses during Interim semesters";
		assert_eq!(expected, input.print().unwrap());
	}

	#[test]
	fn pretty_print_inline_terms() {
		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: { gereqs: FOL-C }, what: terms, do: count >= 2}").unwrap();
		let expected =
			"take enough courses with the “FOL-C” general education attribute to span at least two terms";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
			serde_yaml::from_str(&"{given: courses, where: { semester: Interim }, what: terms, do: count >= 3}")
				.unwrap();
		let expected = "take enough courses during Interim semesters to span at least three terms";
		assert_eq!(expected, input.print().unwrap());
	}

	#[test]
	fn pretty_print_inline_given_requirements_what_courses() {
		let input: Rule =
            serde_yaml::from_str(&"{given: these requirements, requirements: [{requirement: Core}, {requirement: Modern}], what: credits, do: sum >= 1}").unwrap();
		let expected = "take enough courses to obtain at least one credit from among courses matched by the “Core” and “Modern” requirements";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
            serde_yaml::from_str(&"{given: these requirements, requirements: [{requirement: Core}, {requirement: Modern}], where: { gereqs: FOL-C }, what: credits, do: sum >= 1}").unwrap();
		let expected = "take enough courses with the “FOL-C” general education attribute to obtain at least one credit from among courses matched by the “Core” and “Modern” requirements";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
            serde_yaml::from_str(&"{given: these requirements, requirements: [{requirement: Core}, {requirement: Modern}], where: { semester: Interim }, what: credits, do: sum >= 3}")
                .unwrap();
		let expected = "take enough courses during Interim semesters to obtain at least three credits from among courses matched by the “Core” and “Modern” requirements";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
            serde_yaml::from_str(&"{given: these requirements, requirements: [{requirement: Core}, {requirement: Modern}], where: { semester: Fall }, what: credits, do: sum >= 10}").unwrap();
		let expected = "take enough courses during Fall semesters to obtain at least ten credits from among courses matched by the “Core” and “Modern” requirements";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
            serde_yaml::from_str(&"{given: these requirements, requirements: [{requirement: Core}, {requirement: Modern}], where: { year: '2012' }, what: credits, do: sum >= 1}").unwrap();
		let expected = "take enough courses during the 2012-13 academic year to obtain at least one credit from among courses matched by the “Core” and “Modern” requirements";
		assert_eq!(expected, input.print().unwrap());

		let input: Rule =
            serde_yaml::from_str(&"{given: these requirements, requirements: [{requirement: Core}, {requirement: Modern}], where: { institution: St. Olaf College }, what: credits, do: sum >= 17}").unwrap();
		let expected = "take enough courses at St. Olaf College to obtain at least 17 credits from among courses matched by the “Core” and “Modern” requirements";
		assert_eq!(expected, input.print().unwrap());
	}
}

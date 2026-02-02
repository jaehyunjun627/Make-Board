<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
	
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Insert title here</title>
<link rel="stylesheet" type=" text/css" href="../css/addrlist.css" />

</head>
<body>
	<div class="container">
		<form action="addr_add.jsp" method="post">
			<label>이름</label> <input type="text" name="username" placeholder="이름"
				required /><br /> <label>전화번호</label> <input type="text"
				name="tel" placeholder="전화번호" required><br /> <label>이메일</label>
			<input type="text" name="email" placeholder="이메일" required><br />
			<label>성별</label><br /> <select name="gender">
				<option value="남">남</option>
				<option value="여">여</option>
			</select>
			<p></p>
			<div>
				<input type="submit" value="등록" />
				<p></p>
				<input type="reset" value="취소" />

			</div>
		</form>
	</div>

</body>
</html>
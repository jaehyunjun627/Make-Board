<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Insert title here</title>
<link rel="stylesheet" type="text.css" href=../css/page_control.css/>
</head>
<body>
<h2>forward_SendRedirect</h2>
<hr />
<form action="forward_action.jsp" method="post">
	forward_action: <input type="text" name=username />
	<input type="submit" value ="Request" />
</form>
<p></p>
<hr />
<p></p>
<form action="responce_sendRedirect.jsp" method="post">
responce_sendRedirect :  <input type="text" name=username />
	<input type="submit" value ="Response" />
</form>
</body>
</html>